/**
 * ConfirmPage Component
 * Email verification interface
 */

import React, { useState } from 'react';
import { useNavigate, useLocation, Link as RouterLink } from 'react-router-dom';
import { useForm } from 'react-hook-form';
import {
  Button,
  FormControl,
  FormLabel,
  FormErrorMessage,
  Input,
  VStack,
  Text,
  Link,
  Alert,
  AlertIcon
} from '@chakra-ui/react';
import { validateVerificationCode, validateEmail } from '@pantry-app/shared';
import { useAuthContext } from '../contexts/AuthContext';
import AuthLayout from '../components/AuthLayout';
import ErrorMessage from '../components/ErrorMessage';

export default function ConfirmPage() {
  const navigate = useNavigate();
  const location = useLocation();
  const { confirmSignup, error, clearError } = useAuthContext();
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [showSuccess, setShowSuccess] = useState(false);

  // Get email from navigation state (passed from signup)
  const emailFromState = location.state?.email || '';

  const {
    register,
    handleSubmit,
    formState: { errors }
  } = useForm({
    defaultValues: {
      email: emailFromState
    }
  });

  const onSubmit = async (data) => {
    setIsSubmitting(true);
    clearError();

    const result = await confirmSignup(data.email, data.code);

    if (result.success) {
      setShowSuccess(true);
      setTimeout(() => {
        navigate('/login');
      }, 2000);
    } else {
      setIsSubmitting(false);
    }
  };

  return (
    <AuthLayout title="Verify Your Email">
      <form onSubmit={handleSubmit(onSubmit)}>
        <VStack spacing={4}>
          {showSuccess ? (
            <Alert status="success" borderRadius="md">
              <AlertIcon />
              Email verified! Redirecting to login...
            </Alert>
          ) : (
            <>
              <Text fontSize="sm" color="gray.600">
                We've sent a verification code to your email. Please enter it below.
              </Text>

              <ErrorMessage error={error} />

              <FormControl isInvalid={errors.email}>
                <FormLabel>Email</FormLabel>
                <Input
                  type="email"
                  {...register('email', {
                    required: 'Email is required',
                    validate: validateEmail
                  })}
                  autoComplete="email"
                />
                <FormErrorMessage>
                  {errors.email?.message}
                </FormErrorMessage>
              </FormControl>

              <FormControl isInvalid={errors.code}>
                <FormLabel>Verification Code</FormLabel>
                <Input
                  type="text"
                  placeholder="123456"
                  {...register('code', {
                    required: 'Verification code is required',
                    validate: validateVerificationCode
                  })}
                  autoComplete="one-time-code"
                />
                <FormErrorMessage>
                  {errors.code?.message}
                </FormErrorMessage>
              </FormControl>

              <Button
                type="submit"
                width="full"
                isLoading={isSubmitting}
                loadingText="Verifying..."
              >
                Verify Email
              </Button>

              <Text fontSize="sm">
                Already verified?{' '}
                <Link as={RouterLink} to="/login" color="brand.500">
                  Log in
                </Link>
              </Text>
            </>
          )}
        </VStack>
      </form>
    </AuthLayout>
  );
}
