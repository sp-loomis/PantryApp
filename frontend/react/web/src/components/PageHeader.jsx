/**
 * PageHeader
 *
 * Consistent screen header: optional back button, title/subtitle, optional
 * right-aligned actions.
 */

import { useNavigate } from 'react-router-dom';
import { Flex, Box, Heading, Text, IconButton } from '@chakra-ui/react';
import { BackIcon } from './icons';

export default function PageHeader({ title, subtitle, back, actions }) {
  const navigate = useNavigate();

  const handleBack = () => {
    if (typeof back === 'string') navigate(back);
    else navigate(-1);
  };

  return (
    <Flex align="center" gap={3} mb={5}>
      {back && (
        <IconButton
          aria-label="Go back"
          icon={<BackIcon boxSize={5} />}
          variant="ghost"
          colorScheme="gray"
          onClick={handleBack}
        />
      )}
      <Box flex="1" minW={0}>
        <Heading size="lg" noOfLines={1}>
          {title}
        </Heading>
        {subtitle && (
          <Text color="gray.500" fontSize="sm" noOfLines={1}>
            {subtitle}
          </Text>
        )}
      </Box>
      {actions}
    </Flex>
  );
}
