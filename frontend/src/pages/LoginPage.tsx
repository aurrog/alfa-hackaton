import { Alert, Badge, Box, Button, Card, Divider, Grid, Group, PasswordInput, ScrollArea, Stack, Text, TextInput, ThemeIcon, Title, UnstyledButton } from '@mantine/core';
import { IconBuildingBank, IconChecks, IconFileSearch, IconRoute, IconUser } from '@tabler/icons-react';
import { useQuery } from '@tanstack/react-query';
import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { api, errorText } from '../api/client';
import { useAuth } from '../auth/AuthContext';
import { Logo } from '../layouts/ClientLayout';

interface Demo {
  email: string;
  full_name: string;
  kind: string;
  note: string;
  company?: string | null;
  role_title?: string | null;
}

const VALUE = [
  { icon: IconRoute, title: 'Путь от задачи до денег на счёте', text: 'Подбор под задачу, заявка с автозаполнением, решение, подпись и выдача — в одном кабинете.' },
  { icon: IconFileSearch, title: 'Не спрашиваем то, что уже известно', text: 'Реквизиты из ЕГРЮЛ, выручка — из оборотов в банке или выписки 1С. У каждого поля видно, откуда оно.' },
  { icon: IconChecks, title: 'Понятное решение', text: 'Если сумма непосильна — контрпредложение. Если отказ — причины простыми словами и план действий.' },
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

  const row = (a: Demo) => (
    <UnstyledButton key={a.email} onClick={() => doLogin(a.email, demo.data!.password)} p="xs" style={{ borderRadius: 10, border: '1px solid var(--line)' }} disabled={!!busy}>
      <Group wrap="nowrap" gap="sm" align="flex-start">
        <ThemeIcon variant="light" color={a.kind === 'bank' ? 'violet' : 'amber'} radius="xl" size={30}>
          {a.kind === 'bank' ? <IconBuildingBank size={16} /> : <IconUser size={16} />}
        </ThemeIcon>
        <Box style={{ minWidth: 0 }}>
          <Group gap={6}>
            <Text size="sm" fw={600}>
              {a.full_name}
            </Text>
            {a.note.match(/^S\d/) && (
              <Badge size="xs" variant="filled" color="ink.9">
                {a.note.slice(0, 2)}
              </Badge>
            )}
          </Group>
          <Text size="xs" c="dimmed">
            {a.company ?? a.role_title} · {a.email}
          </Text>
          <Text size="xs" mt={2}>
            {a.note.replace(/^S\d · /, '')}
          </Text>
        </Box>
        {busy === a.email && (
          <Text size="xs" c="dimmed" ml="auto">
            вход…
          </Text>
        )}
      </Group>
    </UnstyledButton>
  );

  return (
    <Grid gutter={0} style={{ minHeight: '100vh' }}>
      <Grid.Col span={{ base: 12, md: 5 }} className="hero" p={{ base: 'lg', md: 48 }}>
        <Stack justify="space-between" h="100%" gap="xl">
          <Logo inverted />
          <Box>
            <Title order={1} c="white" fz={{ base: 28, md: 38 }} lh={1.15}>
              Кредит для бизнеса — без визита в банк и без «чёрного ящика»
            </Title>
            <Text className="muted" mt="md" fz="lg">
              Кабинет клиента и рабочее место банка на одной заявке и одном статусе, понятном обеим сторонам.
            </Text>
          </Box>
          <Stack gap="lg">
            {VALUE.map((v) => (
              <Group key={v.title} wrap="nowrap" align="flex-start">
                <ThemeIcon size={38} radius="md" color="route" variant="filled">
                  <v.icon size={20} />
                </ThemeIcon>
                <Box>
                  <Text fw={700} c="white">
                    {v.title}
                  </Text>
                  <Text size="sm" className="muted">
                    {v.text}
                  </Text>
                </Box>
              </Group>
            ))}
          </Stack>
          <Text size="xs" className="muted">
            Прототип. Все компании, люди и данные синтетические; внешние системы смоделированы.
          </Text>
        </Stack>
      </Grid.Col>
      <Grid.Col span={{ base: 12, md: 7 }} p={{ base: 'md', md: 48 }}>
        <Stack maw={640} mx="auto" gap="lg">
          <Card>
            <Title order={2}>Вход</Title>
            <form
              onSubmit={(e) => {
                e.preventDefault();
                void doLogin(email, password);
              }}
            >
              <Stack mt="md" gap="sm">
                <TextInput label="E-mail" value={email} onChange={(e) => setEmail(e.currentTarget.value)} autoComplete="username" required />
                <PasswordInput label="Пароль" value={password} onChange={(e) => setPassword(e.currentTarget.value)} autoComplete="current-password" required />
                {error && (
                  <Alert color="signal" variant="light">
                    {error}
                  </Alert>
                )}
                <Button type="submit" loading={busy === email && !!email}>
                  Войти
                </Button>
              </Stack>
            </form>
          </Card>
          {demo.data && (
            <Card>
              <Group justify="space-between">
                <Title order={3}>Тестовые учётные записи</Title>
                <Badge variant="outline">пароль {demo.data.password}</Badge>
              </Group>
              <Text size="sm" c="dimmed" mt={4}>
                Вход по клику. S1–S8 — сквозные сценарии проверки (см. README).
              </Text>
              <ScrollArea.Autosize mah={620} mt="md" type="auto">
                <Stack gap="xs">
                  <Text size="xs" tt="uppercase" fw={700} c="dimmed">
                    Клиенты
                  </Text>
                  {clients.map(row)}
                  <Divider my="xs" />
                  <Text size="xs" tt="uppercase" fw={700} c="dimmed">
                    Сотрудники банка
                  </Text>
                  {staff.map(row)}
                </Stack>
              </ScrollArea.Autosize>
            </Card>
          )}
        </Stack>
      </Grid.Col>
    </Grid>
  );
}
