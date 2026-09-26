/**
 * Forgot Password Page
 *
 * Step 1 of the reset flow: the user enters their email and Cognito emails a
 * reset code. On success we forward to the reset page with the email prefilled.
 */

import { useState } from 'react';
import { useNavigate, Link as RouterLink } from 'react-router-dom';
import { useForm } from 'react-hook-form';
import {
  FormControl,
  FormLabel,
  Input,
  Button,
  VStack,
  Link,
  Text,
  Alert,
  AlertIcon
} from '@chakra-ui/react';
import { validateEmail } from '@pantry-app/shared';
import { useAuthContext } from '../contexts/AuthContext';
import AuthLayout from '../components/AuthLayout';
import ErrorMessage from '../components/ErrorMessage';

export default function ForgotPasswordPage() {
  const navigate = useNavigate();
  const { requestPasswordReset } = useAuthContext();
  const [error, setError] = useState(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const {
    register,
    handleSubmit,
    formState: { errors }
  } = useForm();

  const onSubmit = async (data) => {
    try {
      setIsSubmitting(true);
      setError(null);

      await requestPasswordReset(data.email);

      // Forward to the reset page with the email prefilled.
      navigate('/reset-password', { state: { email: data.email } });
    } catch (err) {
      setError(err);
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <AuthLayout title="Reset Password">
      <Alert status="info" borderRadius="md" mb={4}>
        <AlertIcon />
        Enter your email and we&apos;ll send you a reset code
      </Alert>

      <ErrorMessage error={error} />

      <form onSubmit={handleSubmit(onSubmit)}>
        <VStack spacing={4}>
          <FormControl isInvalid={errors.email}>
            <FormLabel>Email</FormLabel>
            <Input
              type="email"
              placeholder="you@example.com"
              {...register('email', {
                required: 'Email is required',
                validate: validateEmail
              })}
            />
            {errors.email && (
              <Text color="red.500" fontSize="sm" mt={1}>
                {errors.email.message}
              </Text>
            )}
          </FormControl>

          <Button
            type="submit"
            colorScheme="brand"
            width="full"
            isLoading={isSubmitting}
            loadingText="Sending code..."
          >
            Send Reset Code
          </Button>

          <Text>
            Remembered it?{' '}
            <Link as={RouterLink} to="/login" color="brand.500">
              Sign in
            </Link>
          </Text>
        </VStack>
      </form>
    </AuthLayout>
  );
}
