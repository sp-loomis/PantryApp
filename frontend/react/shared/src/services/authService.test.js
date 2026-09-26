import { describe, it, expect, vi, beforeEach } from 'vitest';

// Mock the Amplify auth layer so we exercise the service wrappers only.
const signOut = vi.fn();
const resetPassword = vi.fn();
const confirmResetPassword = vi.fn();
vi.mock('aws-amplify/auth', () => ({
  signUp: vi.fn(),
  confirmSignUp: vi.fn(),
  signIn: vi.fn(),
  signOut: (...args) => signOut(...args),
  getCurrentUser: vi.fn(),
  resetPassword: (...args) => resetPassword(...args),
  confirmResetPassword: (...args) => confirmResetPassword(...args),
}));

// Mock auth mode so we can toggle the local dev-bypass short-circuit.
const getAuthMode = vi.fn();
vi.mock('../config/env.js', () => ({
  getAuthMode: () => getAuthMode(),
  LOCAL_DEV_USER: { userId: 'local', email: 'local@dev' },
}));

const { requestPasswordReset, confirmPasswordReset, signOutUser } = await import(
  './authService.js'
);

describe('authService password reset', () => {
  beforeEach(() => {
    signOut.mockReset();
    resetPassword.mockReset();
    confirmResetPassword.mockReset();
    getAuthMode.mockReset();
    getAuthMode.mockReturnValue('cognito');
  });

  it('requestPasswordReset calls resetPassword with the email as username', async () => {
    resetPassword.mockResolvedValue({ nextStep: { resetPasswordStep: 'CONFIRM' } });
    const result = await requestPasswordReset('user@example.com');
    expect(resetPassword).toHaveBeenCalledWith({ username: 'user@example.com' });
    expect(result).toEqual({ resetPasswordStep: 'CONFIRM' });
  });

  it('confirmPasswordReset passes username, code, and new password', async () => {
    confirmResetPassword.mockResolvedValue(undefined);
    await confirmPasswordReset('user@example.com', '123456', 'NewPass1');
    expect(confirmResetPassword).toHaveBeenCalledWith({
      username: 'user@example.com',
      confirmationCode: '123456',
      newPassword: 'NewPass1',
    });
  });

  it('rethrows when confirmResetPassword fails', async () => {
    confirmResetPassword.mockRejectedValue(new Error('CodeMismatchException'));
    await expect(
      confirmPasswordReset('user@example.com', '000000', 'NewPass1')
    ).rejects.toThrow('CodeMismatchException');
  });

  it('short-circuits both reset calls in local dev-bypass mode', async () => {
    getAuthMode.mockReturnValue('local');
    const requested = await requestPasswordReset('user@example.com');
    await confirmPasswordReset('user@example.com', '123456', 'NewPass1');
    expect(requested).toBeNull();
    expect(resetPassword).not.toHaveBeenCalled();
    expect(confirmResetPassword).not.toHaveBeenCalled();
  });

  it('signOutUser calls Amplify signOut in cognito mode', async () => {
    signOut.mockResolvedValue(undefined);
    await signOutUser();
    expect(signOut).toHaveBeenCalledTimes(1);
  });

  it('signOutUser is a no-op in local dev-bypass mode', async () => {
    getAuthMode.mockReturnValue('local');
    await signOutUser();
    expect(signOut).not.toHaveBeenCalled();
  });
});
