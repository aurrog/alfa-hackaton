import { Alert, Box, Button, Checkbox, Group, Modal, PasswordInput, Stack, Text, Title } from '@mantine/core';
import { IconFileText, IconSignature } from '@tabler/icons-react';
import { useEffect, useRef, useState, type ReactNode } from 'react';
import { errorText } from '../api/client';
import { CheckDraw, reducedMotion } from '../lib/motion';

interface Props {
  opened: boolean;
  onClose: () => void;
  title: string;
  /** подпись над заголовком, например «Шаг 3 из 3 · Подпись» */
  step?: string;
  documents: string[];
  /** показать согласия БКИ и ПДн (подпись заявки) */
  consents?: { bki: ReactNode; pd: ReactNode };
  onSign: (password: string, consents: { bki: boolean; pd: boolean }) => Promise<unknown>;
  /** вызывается после короткого экрана «Подписано» с результатом onSign */
  onDone?: (result: unknown) => void;
  /** текст экрана успеха */
  doneText?: { title: string; text: string };
  confirmLabel?: string;
}

/** Простая электронная подпись: повторный ввод пароля, фиксация хэша документов, времени и подписанта. */
export function SignModal({ opened, onClose, title, step, documents, consents, onSign, onDone, doneText, confirmLabel = 'Подписать' }: Props) {
  const [password, setPassword] = useState('');
  const [bki, setBki] = useState(false);
  const [pd, setPd] = useState(false);
  const [busy, setBusy] = useState(false);
  const [done, setDone] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const timer = useRef<number | undefined>(undefined);
  const ready = password.length > 0 && (!consents || (bki && pd));
  useEffect(() => () => window.clearTimeout(timer.current), []);

  const submit = async () => {
    setBusy(true);
    setError(null);
    try {
      const result = await onSign(password, { bki, pd });
      setPassword('');
      setDone(true);
      // короткий экран «Подписано», затем — дальше по процессу
      timer.current = window.setTimeout(() => {
        setDone(false);
        onClose();
        onDone?.(result);
      }, reducedMotion() ? 300 : 1300);
    } catch (e) {
      setError(errorText(e));
    } finally {
      setBusy(false);
    }
  };

  if (done) {
    return (
      <Modal opened={opened} onClose={() => undefined} withCloseButton={false} size="sm" centered>
        <Stack align="center" gap={10} py="lg">
          <CheckDraw size={72} />
          <Title order={2} fz={24} mt={8} className="rise" style={{ animationDelay: '200ms' }}>
            {doneText?.title ?? 'Подписано'}
          </Title>
          <Text c="dimmed" ta="center" size="sm" className="rise" style={{ animationDelay: '300ms' }}>
            {doneText?.text ?? 'Документы подписаны простой электронной подписью.'}
          </Text>
        </Stack>
      </Modal>
    );
  }

  return (
    <Modal
      opened={opened}
      onClose={onClose}
      size="lg"
      title={
        <Box>
          {step && (
            <Text size="sm" c="dimmed" fw={400} ff="var(--mantine-font-family)" style={{ letterSpacing: 0 }}>
              {step}
            </Text>
          )}
          {title}
        </Box>
      }
    >
      <Stack gap="lg">
        <Box>
          <Text size="sm" fw={600} mb={8}>
            Вы подписываете
          </Text>
          <div className="rows">
            {documents.map((d) => (
              <Group key={d} gap={10} py={9} wrap="nowrap">
                <IconFileText size={18} color="var(--muted)" style={{ flex: 'none' }} />
                <Text size="sm">{d}</Text>
              </Group>
            ))}
          </div>
        </Box>
        {consents && (
          <Stack gap="sm">
            <Checkbox checked={bki} onChange={(e) => setBki(e.currentTarget.checked)} label={consents.bki} />
            <Checkbox checked={pd} onChange={(e) => setPd(e.currentTarget.checked)} label={consents.pd} />
          </Stack>
        )}
        <PasswordInput
          label="Пароль от кабинета — подтверждение подписи"
          description="В демо-стенде — Demo-2026"
          size="md"
          value={password}
          onChange={(e) => setPassword(e.currentTarget.value)}
          onKeyDown={(e) => e.key === 'Enter' && ready && submit()}
          data-autofocus
        />
        <Text size="xs" c="dimmed">
          Простая электронная подпись: система зафиксирует хэш каждого документа, время, подписанта и IP-адрес. Подпись имеет силу собственноручной в рамках соглашения об электронном документообороте.
        </Text>
        {error && <Alert color="bad">{error}</Alert>}
        <Group justify="flex-end" gap="sm">
          <Button variant="default" size="md" onClick={onClose}>
            Отмена
          </Button>
          <Button color="brand" size="md" leftSection={<IconSignature size={18} />} onClick={submit} loading={busy} disabled={!ready}>
            {confirmLabel}
          </Button>
        </Group>
      </Stack>
    </Modal>
  );
}
