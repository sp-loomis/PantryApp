/**
 * SignupPage Component
 * User signup interface
 */

import React, { useState } from 'react';
import { useNavigate, Link as RouterLink } from 'react-router-dom';
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
  FormHelperText
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
  const { signup, error, clearError } = useAuthContext();
  const [isSubmitting, setIsSubmitting] = useState(false);

  const {
    register,
    handleSubmit,
    watch,
    formState: { errors }
  } = useForm();

  const password = watch('password');

  const onSubmit = async (data) => {
    setIsSubmitting(true);
    clearError();

    const result = await signup(data.email, data.password);

    if (result.success) {
      navigate('/confirm', { state: { email: data.email } });
    } else {
      setIsSubmitting(false);
    }
  };

  return (
    <AuthLayout title="Create Account">
      <form onSubmit={handleSubmit(onSubmit)}>
        <VStack spacing={4}>
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

          <FormControl isInvalid={errors.password}>
            <FormLabel>Password</FormLabel>
            <Input
              type="password"
              {...register('password', {
                required: 'Password is required',
                validate: validatePassword
              })}
              autoComplete="new-password"
            />
            <FormHelperText fontSize="sm" color="gray.600">
              At least 8 characters with uppercase, lowercase, and numbers
            </FormHelperText>
            <FormErrorMessage>
              {errors.password?.message}
            </FormErrorMessage>
          </FormControl>

          <FormControl isInvalid={errors.confirmPassword}>
            <FormLabel>Confirm Password</FormLabel>
            <Input
              type="password"
              {...register('confirmPassword', {
                required: 'Please confirm your password',
                validate: (value) => validatePasswordConfirmation(password, value)
              })}
              autoComplete="new-password"
            />
            <FormErrorMessage>
              {errors.confirmPassword?.message}
            </FormErrorMessage>
          </FormControl>

          <Button
            type="submit"
            width="full"
            isLoading={isSubmitting}
            loadingText="Creating account..."
          >
            Sign Up
          </Button>

          <Text>
            Already have an account?{' '}
            <Link as={RouterLink} to="/login" color="brand.500">
              Log in
            </Link>
          </Text>
        </VStack>
      </form>
    </AuthLayout>
  );
}
