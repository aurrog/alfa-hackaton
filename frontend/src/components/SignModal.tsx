import { Alert, Button, Checkbox, Group, List, Modal, PasswordInput, Stack, Text, ThemeIcon } from '@mantine/core';
import { IconFileCheck, IconSignature } from '@tabler/icons-react';
import { useState, type ReactNode } from 'react';
import { errorText } from '../api/client';

interface Props {
  opened: boolean;
  onClose: () => void;
  title: string;
  documents: string[];
  /** показать согласия БКИ и ПДн (подпись заявки) */
  consents?: { bki: ReactNode; pd: ReactNode };
  onSign: (password: string, consents: { bki: boolean; pd: boolean }) => Promise<unknown>;
  confirmLabel?: string;
}

/** Простая электронная подпись: повторный ввод пароля, фиксация хэша документов, времени и подписанта. */
export function SignModal({ opened, onClose, title, documents, consents, onSign, confirmLabel = 'Подписать' }: Props) {
  const [password, setPassword] = useState('');
  const [bki, setBki] = useState(false);
  const [pd, setPd] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const ready = password.length > 0 && (!consents || (bki && pd));

  const submit = async () => {
    setBusy(true);
    setError(null);
    try {
      await onSign(password, { bki, pd });
      setPassword('');
      onClose();
    } catch (e) {
      setError(errorText(e));
    } finally {
      setBusy(false);
    }
  };

  return (
    <Modal opened={opened} onClose={onClose} title={<Text fw={700}>{title}</Text>} size="lg" centered>
      <Stack>
        <Text size="sm" c="dimmed">
          Вы подписываете документы простой электронной подписью. Система зафиксирует хэш каждого документа, время,
          подписанта и IP-адрес — подпись имеет силу собственноручной в рамках соглашения об электронном документообороте.
        </Text>
        <List spacing={6} size="sm" icon={<ThemeIcon size={20} radius="xl" variant="light"><IconFileCheck size={13} /></ThemeIcon>}>
          {documents.map((d) => (
            <List.Item key={d}>{d}</List.Item>
          ))}
        </List>
        {consents && (
          <Stack gap="xs">
            <Checkbox checked={bki} onChange={(e) => setBki(e.currentTarget.checked)} label={consents.bki} />
            <Checkbox checked={pd} onChange={(e) => setPd(e.currentTarget.checked)} label={consents.pd} />
          </Stack>
        )}
        <PasswordInput
          label="Пароль от кабинета"
          description="Подтверждение подписи. В демо-стенде — Demo-2026"
          value={password}
          onChange={(e) => setPassword(e.currentTarget.value)}
          onKeyDown={(e) => e.key === 'Enter' && ready && submit()}
          data-autofocus
        />
        {error && (
          <Alert color="signal" variant="light">
            {error}
          </Alert>
        )}
        <Group justify="flex-end">
          <Button variant="default" onClick={onClose}>
            Отмена
          </Button>
          <Button leftSection={<IconSignature size={18} />} onClick={submit} loading={busy} disabled={!ready}>
            {confirmLabel}
          </Button>
        </Group>
      </Stack>
    </Modal>
  );
}
