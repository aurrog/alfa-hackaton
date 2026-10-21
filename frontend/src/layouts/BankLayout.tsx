import { AppShell, Avatar, Badge, Box, Burger, Group, NavLink as MNavLink, ScrollArea, Stack, Text, UnstyledButton } from '@mantine/core';
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
  return (
    <AppShell navbar={{ width: 250, breakpoint: 'sm', collapsed: { mobile: !opened } }} header={{ height: { base: 56, sm: 0 } }} padding="md">
      <AppShell.Header hiddenFrom="sm" px="md">
        <Group h="100%">
          <Burger opened={opened} onClick={toggle} size="sm" aria-label="Меню" />
          <Logo sub="рабочее место банка" />
        </Group>
      </AppShell.Header>
      <AppShell.Navbar p="sm" bg="ink.9" style={{ borderRight: 0 }}>
        <Box px="xs" py="sm" visibleFrom="sm">
          <Logo sub="рабочее место банка" inverted />
        </Box>
        <ScrollArea style={{ flex: 1 }} mt="sm">
          <Stack gap={2}>
            {items.map((it) => {
              const active = it.exact ? loc.pathname === it.to || loc.pathname.startsWith('/bank/applications') : loc.pathname.startsWith(it.to);
              return (
                <MNavLink
                  key={it.to}
                  component={NavLink}
                  to={it.to}
                  label={it.label}
                  onClick={close}
                  leftSection={<it.icon size={18} />}
                  rightSection={it.badge ? <Badge size="sm" color="violet" variant="filled">{it.badge}</Badge> : undefined}
                  active={active}
                  variant="filled"
                  color="route"
                  style={{ borderRadius: 8, color: active ? undefined : '#c9cee0' }}
                />
              );
            })}
          </Stack>
        </ScrollArea>
        <UnstyledButton onClick={logout} p="xs" style={{ borderTop: '1px solid #2a2f40' }}>
          <Group gap="sm" wrap="nowrap">
            <Avatar color="violet" radius="xl">
              {user?.full_name.split(' ').slice(0, 2).map((s) => s[0]).join('')}
            </Avatar>
            <Box style={{ minWidth: 0, flex: 1 }}>
              <Text size="sm" fw={600} c="white" truncate>
                {user?.full_name}
              </Text>
              <Text size="xs" c="#9aa2b8" truncate>
                {user?.role_title}
                {user?.authority_limit ? ` · до ${money(user.authority_limit)}` : ''}
              </Text>
            </Box>
            <IconLogout size={16} color="#9aa2b8" />
          </Group>
        </UnstyledButton>
      </AppShell.Navbar>
      <AppShell.Main>
        <Box maw={1400} mx="auto">
          <Outlet />
        </Box>
      </AppShell.Main>
    </AppShell>
  );
}
