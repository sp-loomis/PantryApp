terraform {
  required_version = ">= 1.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

# ============================================================================
# REST API
# ============================================================================
# A regional REST API that fronts the API Lambda. The backend uses Powertools'
# APIGatewayRestResolver and reads identity from
# `requestContext.authorizer.claims`, so this is a REST API (not HTTP API v2)
# with a Cognito User Pool authorizer performing JWT validation.
resource "aws_api_gateway_rest_api" "api" {
  name        = var.api_name
  description = "Pantry App core API (${var.environment})"

  endpoint_configuration {
    types = ["REGIONAL"]
  }

  tags = merge(
    {
      Name        = var.api_name
      Environment = var.environment
      Project     = "pantry"
    },
    var.tags
  )
}

# ============================================================================
# Cognito authorizer
# ============================================================================
# Validates the `Authorization: Bearer <token>` header against the Cognito user
# pool and injects the JWT claims (sub, cognito:groups, ...) into the request
# context, where auth.py reads them. The frontend sends the ID token.
resource "aws_api_gateway_authorizer" "cognito" {
  name            = "${var.api_name}-cognito"
  rest_api_id     = aws_api_gateway_rest_api.api.id
  type            = "COGNITO_USER_POOLS"
  provider_arns   = [var.cognito_user_pool_arn]
  identity_source = "method.request.header.Authorization"
}

# ============================================================================
# Catch-all proxy resource
# ============================================================================
# `/{proxy+}` matches every application path (/locations, /items, /search, ...).
# The app defines no route at the root "/", so a proxy resource is sufficient.
resource "aws_api_gateway_resource" "proxy" {
  rest_api_id = aws_api_gateway_rest_api.api.id
  parent_id   = aws_api_gateway_rest_api.api.root_resource_id
  path_part   = "{proxy+}"
}

# --- ANY: real requests, authenticated, proxied to Lambda ------------------
resource "aws_api_gateway_method" "proxy_any" {
  rest_api_id   = aws_api_gateway_rest_api.api.id
  resource_id   = aws_api_gateway_resource.proxy.id
  http_method   = "ANY"
  authorization = "COGNITO_USER_POOLS"
  authorizer_id = aws_api_gateway_authorizer.cognito.id

  request_parameters = {
    "method.request.path.proxy" = true
  }
}

resource "aws_api_gateway_integration" "proxy_any" {
  rest_api_id             = aws_api_gateway_rest_api.api.id
  resource_id             = aws_api_gateway_resource.proxy.id
  http_method             = aws_api_gateway_method.proxy_any.http_method
  integration_http_method = "POST"
  type                    = "AWS_PROXY"
  uri                     = var.lambda_invoke_arn
}

# --- OPTIONS: CORS preflight, no auth, MOCK integration --------------------
# Preflight requests carry no Authorization header, so they must bypass the
# Cognito authorizer. A MOCK integration answers them with the CORS headers.
resource "aws_api_gateway_method" "proxy_options" {
  rest_api_id   = aws_api_gateway_rest_api.api.id
  resource_id   = aws_api_gateway_resource.proxy.id
  http_method   = "OPTIONS"
  authorization = "NONE"
}

resource "aws_api_gateway_integration" "proxy_options" {
  rest_api_id = aws_api_gateway_rest_api.api.id
  resource_id = aws_api_gateway_resource.proxy.id
  http_method = aws_api_gateway_method.proxy_options.http_method
  type        = "MOCK"

  request_templates = {
    "application/json" = "{\"statusCode\": 200}"
  }
}

resource "aws_api_gateway_method_response" "proxy_options" {
  rest_api_id = aws_api_gateway_rest_api.api.id
  resource_id = aws_api_gateway_resource.proxy.id
  http_method = aws_api_gateway_method.proxy_options.http_method
  status_code = "200"

  response_models = {
    "application/json" = "Empty"
  }

  response_parameters = {
    "method.response.header.Access-Control-Allow-Headers" = true
    "method.response.header.Access-Control-Allow-Methods" = true
    "method.response.header.Access-Control-Allow-Origin"  = true
  }
}

resource "aws_api_gateway_integration_response" "proxy_options" {
  rest_api_id = aws_api_gateway_rest_api.api.id
  resource_id = aws_api_gateway_resource.proxy.id
  http_method = aws_api_gateway_method.proxy_options.http_method
  status_code = aws_api_gateway_method_response.proxy_options.status_code

  response_parameters = {
    "method.response.header.Access-Control-Allow-Headers" = "'Content-Type,Authorization'"
    "method.response.header.Access-Control-Allow-Methods" = "'GET,POST,PUT,PATCH,DELETE,OPTIONS'"
    "method.response.header.Access-Control-Allow-Origin"  = "'${var.allowed_origin}'"
  }

  depends_on = [aws_api_gateway_integration.proxy_options]
}

# ============================================================================
# Slack OAuth callback — explicit path, NO Cognito authorizer
# ============================================================================
# Slack's redirect hits /slack/oauth/callback with no Authorization header, so
# it must bypass the Cognito authorizer. An explicit resource path outranks the
# greedy {proxy+}, so only this exact path is unauthenticated; trust comes from
# the signed `state` the Lambda verifies. Every other /slack/* path still flows
# through the Cognito-guarded {proxy+}.
resource "aws_api_gateway_resource" "slack" {
  rest_api_id = aws_api_gateway_rest_api.api.id
  parent_id   = aws_api_gateway_rest_api.api.root_resource_id
  path_part   = "slack"
}

resource "aws_api_gateway_resource" "slack_oauth" {
  rest_api_id = aws_api_gateway_rest_api.api.id
  parent_id   = aws_api_gateway_resource.slack.id
  path_part   = "oauth"
}

resource "aws_api_gateway_resource" "slack_oauth_callback" {
  rest_api_id = aws_api_gateway_rest_api.api.id
  parent_id   = aws_api_gateway_resource.slack_oauth.id
  path_part   = "callback"
}

resource "aws_api_gateway_method" "slack_oauth_callback" {
  rest_api_id   = aws_api_gateway_rest_api.api.id
  resource_id   = aws_api_gateway_resource.slack_oauth_callback.id
  http_method   = "GET"
  authorization = "NONE"
}

resource "aws_api_gateway_integration" "slack_oauth_callback" {
  rest_api_id             = aws_api_gateway_rest_api.api.id
  resource_id             = aws_api_gateway_resource.slack_oauth_callback.id
  http_method             = aws_api_gateway_method.slack_oauth_callback.http_method
  integration_http_method = "POST"
  type                    = "AWS_PROXY"
  uri                     = var.lambda_invoke_arn
}

# ============================================================================
# CORS on gateway-generated error responses
# ============================================================================
# Errors raised by API Gateway itself (e.g. a 401 from the authorizer) never
# reach the Lambda, so without these the browser sees an opaque CORS failure
# instead of the real status. Attach the ACAO header to the default error
# responses so the SPA can read them.
resource "aws_api_gateway_gateway_response" "default_4xx" {
  rest_api_id   = aws_api_gateway_rest_api.api.id
  response_type = "DEFAULT_4XX"

  response_parameters = {
    "gatewayresponse.header.Access-Control-Allow-Origin"  = "'${var.allowed_origin}'"
    "gatewayresponse.header.Access-Control-Allow-Headers" = "'Content-Type,Authorization'"
  }
}

resource "aws_api_gateway_gateway_response" "default_5xx" {
  rest_api_id   = aws_api_gateway_rest_api.api.id
  response_type = "DEFAULT_5XX"

  response_parameters = {
    "gatewayresponse.header.Access-Control-Allow-Origin"  = "'${var.allowed_origin}'"
    "gatewayresponse.header.Access-Control-Allow-Headers" = "'Content-Type,Authorization'"
  }
}

# ============================================================================
# Deployment + stage
# ============================================================================
resource "aws_api_gateway_deployment" "deployment" {
  rest_api_id = aws_api_gateway_rest_api.api.id

  # Force a new deployment whenever the API surface changes. Hashing the
  # relevant resource definitions keeps this in sync without manual bumps.
  triggers = {
    redeployment = sha1(jsonencode([
      aws_api_gateway_resource.proxy.id,
      aws_api_gateway_method.proxy_any.id,
      aws_api_gateway_integration.proxy_any.id,
      aws_api_gateway_method.proxy_options.id,
      aws_api_gateway_integration.proxy_options.id,
      aws_api_gateway_integration_response.proxy_options.id,
      aws_api_gateway_authorizer.cognito.id,
      aws_api_gateway_gateway_response.default_4xx.id,
      aws_api_gateway_gateway_response.default_5xx.id,
      aws_api_gateway_resource.slack_oauth_callback.id,
      aws_api_gateway_method.slack_oauth_callback.id,
      aws_api_gateway_integration.slack_oauth_callback.id,
    ]))
  }

  lifecycle {
    create_before_destroy = true
  }
}

resource "aws_api_gateway_stage" "stage" {
  rest_api_id   = aws_api_gateway_rest_api.api.id
  deployment_id = aws_api_gateway_deployment.deployment.id
  stage_name    = var.environment

  tags = merge(
    {
      Name        = "${var.api_name}-${var.environment}"
      Environment = var.environment
      Project     = "pantry"
    },
    var.tags
  )
}

# ============================================================================
# Allow API Gateway to invoke the Lambda
# ============================================================================
resource "aws_lambda_permission" "apigw" {
  statement_id  = "AllowAPIGatewayInvoke"
  action        = "lambda:InvokeFunction"
  function_name = var.lambda_function_name
  principal     = "apigateway.amazonaws.com"

  # Scope to this API (any method/path/stage).
  source_arn = "${aws_api_gateway_rest_api.api.execution_arn}/*/*"
}
