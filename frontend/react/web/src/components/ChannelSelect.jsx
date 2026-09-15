/**
 * ChannelSelect
 *
 * A <Select> of the channels available to a Slack connection. Unlike
 * LocationSelect (which reads from context), channels are fetched per
 * connection on mount via the Slack service.
 */

import { useEffect, useState } from 'react';
import { Select } from '@chakra-ui/react';
import { listChannels } from '@pantry-app/shared';

export default function ChannelSelect({ connectionId, value, onChange, placeholder = 'Select a channel', ...props }) {
  const [channels, setChannels] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let active = true;
    setLoading(true);
    listChannels(connectionId)
      .then((chs) => { if (active) setChannels(chs); })
      .catch(() => { if (active) setChannels([]); })
      .finally(() => { if (active) setLoading(false); });
    return () => { active = false; };
  }, [connectionId]);

  return (
    <Select
      value={value}
      onChange={onChange}
      placeholder={loading ? 'Loading channels…' : placeholder}
      isDisabled={loading}
      {...props}
    >
      {channels.map((ch) => (
        <option key={ch.id} value={ch.id}>
          #{ch.name}
        </option>
      ))}
    </Select>
  );
}
