/**
 * Signup Page
 *
 * User registration with email and password.
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
  Text
} from '@chakra-ui/react';
import {
  validateEmail,
  validatePassword,
  validatePasswordConfirmation
} from '@pantry-app/shared';
import { useAuthContext } from '../contexts/AuthContext';
import AuthLayout from '../components/AuthLayout';
import ErrorMessage from '../components/ErrorMessage';

export default function SignupPage() {
  const navigate = useNavigate();
  const { signup } = useAuthContext();
  const [error, setError] = useState(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const {
    register,
    handleSubmit,
    watch,
    formState: { errors }
  } = useForm();

  const password = watch('password');

  const onSubmit = async (data) => {
    try {
      setIsSubmitting(true);
      setError(null);

      await signup(data.email, data.password);

      // Navigate to confirmation page with email
      navigate('/confirm', { state: { email: data.email } });
    } catch (err) {
      setError(err);
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <AuthLayout title="Create Account">
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

          <FormControl isInvalid={errors.password}>
            <FormLabel>Password</FormLabel>
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
            <FormLabel>Confirm Password</FormLabel>
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
            loadingText="Creating account..."
          >
            Sign Up
          </Button>

          <Text>
            Already have an account?{' '}
            <Link as={RouterLink} to="/login" color="brand.500">
              Sign in
            </Link>
          </Text>
        </VStack>
      </form>
    </AuthLayout>
  );
}
