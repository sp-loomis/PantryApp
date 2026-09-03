/**
 * ConfirmDialog
 *
 * Controlled confirmation dialog for destructive actions (e.g. delete).
 */

import { useRef } from 'react';
import {
  AlertDialog,
  AlertDialogOverlay,
  AlertDialogContent,
  AlertDialogHeader,
  AlertDialogBody,
  AlertDialogFooter,
  Button,
} from '@chakra-ui/react';

export default function ConfirmDialog({
  isOpen,
  onClose,
  onConfirm,
  title,
  body,
  confirmLabel = 'Delete',
  isLoading = false,
}) {
  const cancelRef = useRef();

  return (
    <AlertDialog
      isOpen={isOpen}
      leastDestructiveRef={cancelRef}
      onClose={onClose}
      isCentered
    >
      <AlertDialogOverlay>
        <AlertDialogContent mx={4}>
          <AlertDialogHeader fontSize="lg" fontWeight="bold">
            {title}
          </AlertDialogHeader>
          <AlertDialogBody>{body}</AlertDialogBody>
          <AlertDialogFooter>
            <Button ref={cancelRef} onClick={onClose} variant="ghost" colorScheme="gray">
              Cancel
            </Button>
            <Button colorScheme="red" onClick={onConfirm} ml={3} isLoading={isLoading}>
              {confirmLabel}
            </Button>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialogOverlay>
    </AlertDialog>
  );
}
