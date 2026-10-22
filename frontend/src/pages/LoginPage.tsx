import { Alert, Box, Button, Grid, Group, Loader, PasswordInput, Stack, Text, TextInput, Title, UnstyledButton } from '@mantine/core';
import { IconChevronRight } from '@tabler/icons-react';
import { useQuery } from '@tanstack/react-query';
import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { api, errorText } from '../api/client';
import { useAuth } from '../auth/AuthContext';
import { Tag } from '../components/ui';
import { Logo } from '../layouts/ClientLayout';

interface Demo {
  email: string;
  full_name: string;
  kind: string;
  note: string;
  company?: string | null;
  role_title?: string | null;
}

const HOW = [
  ['Рассчитайте сумму и платёж', 'ещё до заявки — по цели, сумме и сроку'],
  ['Проверьте данные', 'реквизиты из ЕГРЮЛ, выручка — из оборотов по счёту или выписки'],
  ['Подпишите в кабинете', 'решение за минуты, если сумма в пределах лимита — деньги в тот же день'],
];

export function LoginPage() {
  const { login } = useAuth();
  const nav = useNavigate();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const demo = useQuery({ queryKey: ['demo-accounts'], queryFn: () => api.get<{ password: string; accounts: Demo[] }>('/api/v1/auth/demo-accounts'), retry: false });

  const doLogin = async (e: string, p: string) => {
    setBusy(e);
    setError(null);
    try {
      const u = await login(e, p);
      nav(u.kind === 'bank' ? '/bank' : '/', { replace: true });
    } catch (err) {
      setError(errorText(err));
    } finally {
      setBusy(null);
    }
  };

  const clients = demo.data?.accounts.filter((a) => a.kind === 'client') ?? [];
  const staff = demo.data?.accounts.filter((a) => a.kind === 'bank') ?? [];

  const row = (a: Demo) => {
    const scenario = /^S\d/.exec(a.note)?.[0];
    return (
      <UnstyledButton key={a.email} className="row" onClick={() => doLogin(a.email, demo.data!.password)} disabled={!!busy} style={{ padding: '12px 4px' }}>
        <Box style={{ flex: 1, minWidth: 0 }}>
          <Group gap={8} wrap="nowrap">
            <Text size="sm" fw={600} className="row-title" truncate>
              {a.full_name}
            </Text>
            {scenario && <Tag tone="ink">{scenario}</Tag>}
          </Group>
          <Text size="xs" c="dimmed" truncate>
            {a.company ?? a.role_title} · {a.email}
          </Text>
          <Text size="xs" mt={2} c="var(--ink-2)">
            {a.note.replace(/^S\d · /, '')}
          </Text>
        </Box>
        {busy === a.email ? <Loader size="xs" color="ink" /> : <IconChevronRight size={18} color="var(--muted)" />}
      </UnstyledButton>
    );
  };

  return (
    <Grid gutter={0} mih="100vh">
      <Grid.Col span={{ base: 12, md: 6 }} p={{ base: 20, sm: 40, md: 56 }}>
        <Stack justify="space-between" gap={40} className="login-aside">
          <Logo />
          <Box maw={540}>
            <Title order={1} fz={{ base: 32, sm: 44 }} lh={1.08}>
              Кредит для бизнеса в одном окне — от расчёта до денег на счёте
            </Title>
            <Text c="dimmed" fz={17} mt={18} maw={480}>
              Без визита в банк и без «чёрного ящика»: видно, что происходит с заявкой и почему банк принял такое решение.
            </Text>
            <Stack gap={18} mt={36}>
              {HOW.map(([t, d], i) => (
                <Group key={t} gap={16} wrap="nowrap" align="flex-start">
                  <Text className="display" fw={700} fz={15} w={28} h={28} ta="center" lh="28px" style={{ borderRadius: 8, background: 'var(--plate)', flex: 'none' }}>
                    {i + 1}
                  </Text>
                  <Box>
                    <Text fw={600}>{t}</Text>
                    <Text size="sm" c="dimmed">
                      {d}
                    </Text>
                  </Box>
                </Group>
              ))}
            </Stack>
          </Box>
          <Text size="xs" c="dimmed" maw={480}>
            Прототип для кейса. Компании, люди и данные синтетические, внешние системы смоделированы.
          </Text>
        </Stack>
      </Grid.Col>
      <Grid.Col span={{ base: 12, md: 6 }} bg="var(--plate)" p={{ base: 16, sm: 40, md: 56 }}>
        <Stack maw={520} mx="auto" gap="lg">
          <Box bg="#fff" p={{ base: 20, sm: 28 }} style={{ borderRadius: 24 }}>
            <Title order={2}>Вход</Title>
            <form
              onSubmit={(e) => {
                e.preventDefault();
                void doLogin(email, password);
              }}
            >
              <Stack mt="lg" gap="sm">
                <TextInput label="Электронная почта" size="md" value={email} onChange={(e) => setEmail(e.currentTarget.value)} autoComplete="username" required />
                <PasswordInput label="Пароль" size="md" value={password} onChange={(e) => setPassword(e.currentTarget.value)} autoComplete="current-password" required />
                {error && <Alert color="bad">{error}</Alert>}
                <Button type="submit" size="md" mt={6} loading={busy === email && !!email}>
                  Войти
                </Button>
              </Stack>
            </form>
          </Box>
          {demo.data && (
            <Box bg="#fff" p={{ base: 20, sm: 28 }} style={{ borderRadius: 24 }}>
              <Group justify="space-between" align="flex-end">
                <Title order={3}>Тестовые учётные записи</Title>
                <Text size="sm" c="dimmed">
                  пароль <b style={{ color: 'var(--ink)' }}>{demo.data.password}</b>
                </Text>
              </Group>
              <Text size="sm" c="dimmed" mt={4}>
                Вход по клику. S1–S8 — сквозные сценарии из README.
              </Text>
              <Text size="sm" fw={600} mt="lg">
                Клиенты
              </Text>
              <div className="rows">{clients.map(row)}</div>
              <Text size="sm" fw={600} mt="lg">
                Сотрудники банка
              </Text>
              <div className="rows">{staff.map(row)}</div>
            </Box>
          )}
        </Stack>
      </Grid.Col>
    </Grid>
  );
}
