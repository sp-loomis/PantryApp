/**
 * Email Confirmation Page
 *
 * User enters verification code from email.
 */

import { useState } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { useForm } from 'react-hook-form';
import {
  FormControl,
  FormLabel,
  Input,
  Button,
  VStack,
  Text,
  Alert,
  AlertIcon
} from '@chakra-ui/react';
import { validateEmail, validateVerificationCode } from '@pantry-app/shared';
import { useAuthContext } from '../contexts/AuthContext';
import AuthLayout from '../components/AuthLayout';
import ErrorMessage from '../components/ErrorMessage';

export default function ConfirmPage() {
  const navigate = useNavigate();
  const location = useLocation();
  const { confirmSignup } = useAuthContext();
  const [error, setError] = useState(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  // Get email from navigation state (passed from signup page)
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
    try {
      setIsSubmitting(true);
      setError(null);

      await confirmSignup(data.email, data.code);

      // Navigate to login on successful confirmation
      navigate('/login', {
        state: { message: 'Email confirmed! You can now sign in.' }
      });
    } catch (err) {
      setError(err);
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <AuthLayout title="Verify Email">
      <Alert status="info" borderRadius="md" mb={4}>
        <AlertIcon />
        Check your email for a verification code
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
            <FormLabel>Verification Code</FormLabel>
            <Input
              type="text"
              placeholder="123456"
              maxLength={6}
              {...register('code', {
                required: 'Verification code is required',
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

          <Button
            type="submit"
            colorScheme="brand"
            width="full"
            isLoading={isSubmitting}
            loadingText="Verifying..."
          >
            Verify Email
          </Button>
        </VStack>
      </form>
    </AuthLayout>
  );
}
