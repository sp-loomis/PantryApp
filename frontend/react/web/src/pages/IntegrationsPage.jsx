/**
 * IntegrationsPage — connect and manage Slack workspaces.
 *
 * Lists the user's connected Slack workspaces. "Connect Slack" starts OAuth via
 * a full-page redirect to the authorize URL the backend builds. Each connection
 * can post a test message to a chosen channel or be disconnected (revoke +
 * delete). In local auth mode a dev-stub button creates a fake connection so the
 * UI works without real Slack.
 *
 * The OAuth callback redirects back here with ?slack=connected|error, surfaced
 * as a toast.
 */

import { useCallback, useEffect, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import {
  Badge,
  Box,
  Button,
  Center,
  Flex,
  Heading,
  HStack,
  IconButton,
  Spinner,
  Text,
  useDisclosure,
  useToast,
  VStack,
} from '@chakra-ui/react';
import {
  getAuthorizeUrl,
  listConnections,
  disconnectSlack,
  testSlackConnection,
  devStubConnectSlack,
  getAuthMode,
} from '@pantry-app/shared';
import EmptyState from '../components/EmptyState';
import ErrorMessage from '../components/ErrorMessage';
import ConfirmDialog from '../components/ConfirmDialog';
import ChannelSelect from '../components/ChannelSelect';
import { SlackIcon, TrashIcon, RunIcon } from '../components/icons';

export default function IntegrationsPage() {
  const toast = useToast();
  const [searchParams, setSearchParams] = useSearchParams();
  const [connections, setConnections] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [connecting, setConnecting] = useState(false);
  const [channelByConn, setChannelByConn] = useState({});
  const [testingId, setTestingId] = useState(null);
  const [pendingDisconnect, setPendingDisconnect] = useState(null);
  const [disconnecting, setDisconnecting] = useState(false);
  const confirm = useDisclosure();

  const isLocal = getAuthMode() === 'local';

  const load = useCallback(async () => {
    try {
      setError(null);
      setConnections(await listConnections());
    } catch (err) {
      setError(err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  // Surface the OAuth callback result, then clear the query param.
  useEffect(() => {
    const status = searchParams.get('slack');
    if (!status) return;
    if (status === 'connected') {
      toast({ title: 'Slack connected', status: 'success', duration: 5000, isClosable: true });
    } else if (status === 'error') {
      toast({
        title: 'Slack connection failed',
        description: 'Please try connecting again.',
        status: 'error',
        duration: 6000,
        isClosable: true,
      });
    }
    searchParams.delete('slack');
    setSearchParams(searchParams, { replace: true });
  }, [searchParams, setSearchParams, toast]);

  const handleConnect = async () => {
    setConnecting(true);
    try {
      // Full-page redirect to Slack — not a fetch (Slack renders the consent UI).
      window.location.href = await getAuthorizeUrl();
    } catch (err) {
      setError(err);
      setConnecting(false);
    }
  };

  const handleDevStub = async () => {
    try {
      await devStubConnectSlack();
      await load();
    } catch (err) {
      setError(err);
    }
  };

  const handleTest = async (connectionId) => {
    const channelId = channelByConn[connectionId];
    if (!channelId) return;
    setTestingId(connectionId);
    try {
      await testSlackConnection(connectionId, channelId);
      toast({ title: 'Test message sent ✅', status: 'success', duration: 5000, isClosable: true });
    } catch (err) {
      setError(err);
    } finally {
      setTestingId(null);
    }
  };

  const askDisconnect = (connection) => {
    setPendingDisconnect(connection);
    confirm.onOpen();
  };

  const handleDisconnect = async () => {
    if (!pendingDisconnect) return;
    setDisconnecting(true);
    try {
      await disconnectSlack(pendingDisconnect.connection_id);
      confirm.onClose();
      setPendingDisconnect(null);
      await load();
    } catch (err) {
      setError(err);
    } finally {
      setDisconnecting(false);
    }
  };

  return (
    <Box>
      <Flex align="center" justify="space-between" mb={4} gap={3}>
        <Text fontSize="2xl" fontWeight="bold">
          Integrations
        </Text>
        <HStack>
          {isLocal && (
            <Button variant="outline" onClick={handleDevStub}>
              Add dev stub
            </Button>
          )}
          <Button
            leftIcon={<SlackIcon boxSize={4} />}
            onClick={handleConnect}
            isLoading={connecting}
          >
            Connect Slack
          </Button>
        </HStack>
      </Flex>

      <ErrorMessage error={error} />

      {loading ? (
        <Center py={12}>
          <Spinner color="brand.500" thickness="3px" />
        </Center>
      ) : connections.length === 0 ? (
        <EmptyState
          title="No Slack workspaces connected"
          description="Connect your Slack workspace to receive scheduled reports and notifications."
          action={
            <Button mt={2} leftIcon={<SlackIcon boxSize={4} />} onClick={handleConnect} isLoading={connecting}>
              Connect Slack
            </Button>
          }
        />
      ) : (
        <VStack spacing={3} align="stretch">
          {connections.map((conn) => (
            <Box
              key={conn.connection_id}
              bg="white"
              borderWidth="1px"
              borderColor="gray.200"
              borderRadius="lg"
              boxShadow="sm"
              p={4}
            >
              <Flex align="center" justify="space-between" gap={3} mb={3}>
                <HStack spacing={2} minW={0}>
                  <SlackIcon boxSize={5} color="brand.500" />
                  <Heading size="sm" noOfLines={1}>
                    {conn.team_name || 'Slack workspace'}
                  </Heading>
                  <Badge colorScheme="green">Connected</Badge>
                </HStack>
                <IconButton
                  aria-label="Disconnect workspace"
                  icon={<TrashIcon />}
                  size="sm"
                  variant="ghost"
                  colorScheme="red"
                  flexShrink={0}
                  onClick={() => askDisconnect(conn)}
                />
              </Flex>

              <Flex gap={2} align="center" wrap="wrap">
                <Box flex="1" minW="200px">
                  <ChannelSelect
                    connectionId={conn.connection_id}
                    value={channelByConn[conn.connection_id] || ''}
                    onChange={(e) =>
                      setChannelByConn((prev) => ({ ...prev, [conn.connection_id]: e.target.value }))
                    }
                    size="sm"
                  />
                </Box>
                <Button
                  size="sm"
                  variant="outline"
                  leftIcon={<RunIcon />}
                  isLoading={testingId === conn.connection_id}
                  isDisabled={!channelByConn[conn.connection_id]}
                  onClick={() => handleTest(conn.connection_id)}
                >
                  Send test
                </Button>
              </Flex>
            </Box>
          ))}
        </VStack>
      )}

      <ConfirmDialog
        isOpen={confirm.isOpen}
        onClose={confirm.onClose}
        onConfirm={handleDisconnect}
        title="Disconnect Slack"
        body={`Disconnect “${pendingDisconnect?.team_name || 'this workspace'}”? This revokes the bot token and removes the connection.`}
        confirmLabel="Disconnect"
        isLoading={disconnecting}
      />
    </Box>
  );
}
