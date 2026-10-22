import { AppShell, Avatar, Box, Burger, Group, ScrollArea, Stack, Text, UnstyledButton } from '@mantine/core';
import { useDisclosure } from '@mantine/hooks';
import { IconActivityHeartbeat, IconChartBar, IconHistory, IconListCheck, IconLogout, IconScale } from '@tabler/icons-react';
import { useQuery } from '@tanstack/react-query';
import { NavLink, Outlet, useLocation } from 'react-router-dom';
import { api } from '../api/client';
import { useAuth } from '../auth/AuthContext';
import { money } from '../lib/format';
import { Logo } from './ClientLayout';

export function BankLayout() {
  const { user, logout } = useAuth();
  const [opened, { toggle, close }] = useDisclosure(false);
  const loc = useLocation();
  const counts = useQuery({
    queryKey: ['bank-counts'],
    queryFn: () => api.get<{ counts: Record<string, number> }>('/api/v1/bank/queue', { status: 'active' }),
    refetchInterval: 10000,
  });
  const c = counts.data?.counts ?? {};
  const policyRole = user?.bank_role === 'admin' || user?.bank_role === 'risk_manager';
  const items = [
    { to: '/bank', label: 'Очередь заявок', icon: IconListCheck, exact: true, badge: (c.manual_review ?? 0) + (c.committee_review ?? 0) },
    { to: '/bank/dashboard', label: 'Дашборд процесса', icon: IconChartBar },
    { to: '/bank/policy', label: 'Кредитная политика', icon: IconScale },
    { to: '/bank/system', label: 'Мониторинг конвейера', icon: IconActivityHeartbeat },
    ...(policyRole ? [{ to: '/bank/audit', label: 'Журнал аудита', icon: IconHistory }] : []),
  ];
  const initials = user?.full_name.split(' ').slice(0, 2).map((s) => s[0]).join('');
  return (
    <AppShell navbar={{ width: 264, breakpoint: 'sm', collapsed: { mobile: !opened } }} header={{ height: { base: 60, sm: 0 } }} padding={0}>
      <AppShell.Header hiddenFrom="sm" px="md" style={{ borderBottom: '1px solid var(--line)' }}>
        <Group h="100%" gap="sm">
          <Burger opened={opened} onClick={toggle} size="sm" aria-label="Меню" />
          <Logo sub="рабочее место банка" />
        </Group>
      </AppShell.Header>
      <AppShell.Navbar p="md" style={{ borderRight: '1px solid var(--line)' }}>
        <Box px={6} pt={4} pb="lg" visibleFrom="sm">
          <Logo sub="рабочее место банка" />
        </Box>
        <ScrollArea style={{ flex: 1 }}>
          <Stack gap={2}>
            {items.map((it) => {
              const active = it.exact ? loc.pathname === it.to || loc.pathname.startsWith('/bank/applications') : loc.pathname.startsWith(it.to);
              return (
                <UnstyledButton
                  key={it.to}
                  component={NavLink}
                  to={it.to}
                  onClick={close}
                  px={12}
                  py={10}
                  style={{ borderRadius: 12, background: active ? 'var(--plate)' : undefined, color: active ? 'var(--ink)' : 'var(--ink-2)' }}
                >
                  <Group gap={12} wrap="nowrap">
                    <it.icon size={19} stroke={1.7} />
                    <Text size="sm" fw={active ? 600 : 500} style={{ flex: 1 }}>
                      {it.label}
                    </Text>
                    {!!it.badge && (
                      <Text size="xs" fw={700} c="#fff" bg="var(--ink)" px={7} py={1} style={{ borderRadius: 10 }}>
                        {it.badge}
                      </Text>
                    )}
                  </Group>
                </UnstyledButton>
              );
            })}
          </Stack>
        </ScrollArea>
        <UnstyledButton onClick={logout} p={10} mt="sm" style={{ borderRadius: 12, background: 'var(--plate)' }} aria-label="Выйти">
          <Group gap="sm" wrap="nowrap">
            <Avatar color="ink" variant="filled" radius="xl" size={36}>
              {initials}
            </Avatar>
            <Box style={{ minWidth: 0, flex: 1 }}>
              <Text size="sm" fw={600} truncate>
                {user?.full_name}
              </Text>
              <Text size="xs" c="dimmed" truncate>
                {user?.role_title}
                {user?.authority_limit ? ` · до ${money(user.authority_limit)}` : ''}
              </Text>
            </Box>
            <IconLogout size={17} color="var(--muted)" />
          </Group>
        </UnstyledButton>
      </AppShell.Navbar>
      <AppShell.Main>
        <Box maw={1440} mx="auto" px={{ base: 16, sm: 32 }} py={{ base: 20, sm: 36 }}>
          <Outlet />
        </Box>
      </AppShell.Main>
    </AppShell>
  );
}
