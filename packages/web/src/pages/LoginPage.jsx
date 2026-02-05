/**
 * LoginPage Component
 * User login interface
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
  Link
} from '@chakra-ui/react';
import { validateEmail } from '@pantry-app/shared';
import { useAuthContext } from '../contexts/AuthContext';
import AuthLayout from '../components/AuthLayout';
import ErrorMessage from '../components/ErrorMessage';

export default function LoginPage() {
  const navigate = useNavigate();
  const { login, error, clearError } = useAuthContext();
  const [isSubmitting, setIsSubmitting] = useState(false);

  const {
    register,
    handleSubmit,
    formState: { errors }
  } = useForm();

  const onSubmit = async (data) => {
    setIsSubmitting(true);
    clearError();

    const result = await login(data.email, data.password);

    if (result.success) {
      navigate('/');
    } else {
      setIsSubmitting(false);
    }
  };

  return (
    <AuthLayout title="Login to Pantry App">
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
                required: 'Password is required'
              })}
              autoComplete="current-password"
            />
            <FormErrorMessage>
              {errors.password?.message}
            </FormErrorMessage>
          </FormControl>

          <Button
            type="submit"
            width="full"
            isLoading={isSubmitting}
            loadingText="Logging in..."
          >
            Log In
          </Button>

          <Text>
            Don't have an account?{' '}
            <Link as={RouterLink} to="/signup" color="brand.500">
              Sign up
            </Link>
          </Text>
        </VStack>
      </form>
    </AuthLayout>
  );
}
