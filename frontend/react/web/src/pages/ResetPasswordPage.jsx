/**
 * Reset Password Page
 *
 * Step 2 of the reset flow: the user enters the emailed code and a new password.
 * Email is prefilled from navigation state (set by the forgot-password page).
 */

import { useState } from 'react';
import { useNavigate, useLocation, Link as RouterLink } from 'react-router-dom';
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
import {
  validateEmail,
  validateVerificationCode,
  validatePassword,
  validatePasswordConfirmation
} from '@pantry-app/shared';
import { useAuthContext } from '../contexts/AuthContext';
import AuthLayout from '../components/AuthLayout';
import ErrorMessage from '../components/ErrorMessage';

export default function ResetPasswordPage() {
  const navigate = useNavigate();
  const location = useLocation();
  const { confirmPasswordReset } = useAuthContext();
  const [error, setError] = useState(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  // Email passed from the forgot-password page.
  const emailFromState = location.state?.email || '';

  const {
    register,
    handleSubmit,
    watch,
    formState: { errors }
  } = useForm({
    defaultValues: {
      email: emailFromState
    }
  });

  const password = watch('password');

  const onSubmit = async (data) => {
    try {
      setIsSubmitting(true);
      setError(null);

      await confirmPasswordReset(data.email, data.code, data.password);

      navigate('/login', {
        state: { message: 'Password reset. Sign in with your new password.' }
      });
    } catch (err) {
      setError(err);
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <AuthLayout title="Set New Password">
      <Alert status="info" borderRadius="md" mb={4}>
        <AlertIcon />
        Check your email for a reset code
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

          <FormControl isInvalid={errors.code}>
            <FormLabel>Reset Code</FormLabel>
            <Input
              type="text"
              placeholder="123456"
              maxLength={6}
              {...register('code', {
                required: 'Reset code is required',
                validate: validateVerificationCode
              })}
            />
            {errors.code && (
              <Text color="red.500" fontSize="sm" mt={1}>
                {errors.code.message}
              </Text>
            )}
            <Text fontSize="xs" color="gray.600" mt={1}>
              Enter the 6-digit code from your email
            </Text>
          </FormControl>

          <FormControl isInvalid={errors.password}>
            <FormLabel>New Password</FormLabel>
            <Input
              type="password"
              placeholder="At least 8 characters"
              {...register('password', {
                required: 'Password is required',
                validate: validatePassword
              })}
            />
            {errors.password && (
              <Text color="red.500" fontSize="sm" mt={1}>
                {errors.password.message}
              </Text>
            )}
            <Text fontSize="xs" color="gray.600" mt={1}>
              Must contain: uppercase, lowercase, and number
            </Text>
          </FormControl>

          <FormControl isInvalid={errors.confirmPassword}>
            <FormLabel>Confirm New Password</FormLabel>
            <Input
              type="password"
              placeholder="Re-enter your password"
              {...register('confirmPassword', {
                required: 'Please confirm your password',
                validate: (value) => validatePasswordConfirmation(password, value)
              })}
            />
            {errors.confirmPassword && (
              <Text color="red.500" fontSize="sm" mt={1}>
                {errors.confirmPassword.message}
              </Text>
            )}
          </FormControl>

          <Button
            type="submit"
            colorScheme="brand"
            width="full"
            isLoading={isSubmitting}
            loadingText="Resetting..."
          >
            Reset Password
          </Button>

          <Text>
            Back to{' '}
            <Link as={RouterLink} to="/login" color="brand.500">
              Sign in
            </Link>
          </Text>
        </VStack>
      </form>
    </AuthLayout>
  );
}
