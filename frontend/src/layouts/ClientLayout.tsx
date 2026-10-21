import { AppShell, Avatar, Badge, Box, Burger, Button, Container, Drawer, Group, Menu, Select, Stack, Text, UnstyledButton } from '@mantine/core';
import { useDisclosure } from '@mantine/hooks';
import { IconBuildingStore, IconChevronDown, IconLogout, IconPlus } from '@tabler/icons-react';
import { NavLink, Outlet, useLocation, useNavigate } from 'react-router-dom';
import { Assistant } from '../components/Assistant';
import { Notifications } from '../components/Notifications';
import { useAuth } from '../auth/AuthContext';

const NAV = [
  { to: '/', label: 'Главная', exact: true },
  { to: '/products', label: 'Подобрать финансирование' },
  { to: '/applications', label: 'Заявки' },
  { to: '/loans', label: 'Кредиты' },
];

export function Logo({ sub, inverted }: { sub?: string; inverted?: boolean }) {
  return (
    <Group gap={10} wrap="nowrap">
      <svg width="30" height="30" viewBox="0 0 64 64" aria-hidden>
        <rect width="64" height="64" rx="14" fill={inverted ? '#262b3d' : '#14161f'} />
        <path d="M14 44 L26 30 L36 38 L50 20" fill="none" stroke="#3d7bff" strokeWidth="6" strokeLinecap="round" strokeLinejoin="round" />
        <circle cx="50" cy="20" r="6" fill="#b5e853" />
        <circle cx="14" cy="44" r="5" fill="#ffb020" />
      </svg>
      <Box lh={1.1}>
        <Text fw={700} ff="Unbounded, Onest, sans-serif" fz={14} c={inverted ? 'white' : undefined}>
          Кредитный кабинет
        </Text>
        <Text fz={11} c={inverted ? '#9aa2b8' : 'dimmed'}>
          {sub ?? 'для предпринимателей'}
        </Text>
      </Box>
    </Group>
  );
}

function NavItems({ onClick }: { onClick?: () => void }) {
  const loc = useLocation();
  return (
    <>
      {NAV.map((n) => {
        const active = n.exact ? loc.pathname === n.to : loc.pathname.startsWith(n.to);
        return (
          <Button key={n.to} component={NavLink} to={n.to} variant={active ? 'light' : 'subtle'} color={active ? 'route' : 'gray'} onClick={onClick} size="sm">
            {n.label}
          </Button>
        );
      })}
    </>
  );
}

export function ClientLayout() {
  const { user, companies, company, selectCompany, logout } = useAuth();
  const [drawer, { open, close }] = useDisclosure(false);
  const nav = useNavigate();
  return (
    <AppShell header={{ height: 64 }} padding="md">
      <AppShell.Header px="md">
        <Group h="100%" justify="space-between" wrap="nowrap">
          <Group gap="lg" wrap="nowrap">
            <Burger opened={drawer} onClick={open} hiddenFrom="md" size="sm" aria-label="Меню" />
            <UnstyledButton onClick={() => nav('/')}>
              <Logo />
            </UnstyledButton>
            <Group gap={4} visibleFrom="md">
              <NavItems />
            </Group>
          </Group>
          <Group gap="xs" wrap="nowrap">
            {companies.length > 1 ? (
              <Select
                size="xs"
                w={220}
                visibleFrom="sm"
                data={companies.map((c) => ({ value: c.id, label: c.short_name }))}
                value={company?.id ?? null}
                onChange={(v) => v && selectCompany(v)}
                leftSection={<IconBuildingStore size={14} />}
                allowDeselect={false}
              />
            ) : company ? (
              <Badge visibleFrom="sm" variant="outline" color="gray" size="lg" leftSection={<IconBuildingStore size={13} />}>
                {company.short_name}
              </Badge>
            ) : null}
            <Notifications />
            <Menu position="bottom-end" width={260}>
              <Menu.Target>
                <UnstyledButton>
                  <Group gap={6} wrap="nowrap">
                    <Avatar size={32} radius="xl" color="amber">
                      {user?.full_name.split(' ').slice(0, 2).map((s) => s[0]).join('')}
                    </Avatar>
                    <IconChevronDown size={14} />
                  </Group>
                </UnstyledButton>
              </Menu.Target>
              <Menu.Dropdown>
                <Box px="sm" py={6}>
                  <Text size="sm" fw={600}>
                    {user?.full_name}
                  </Text>
                  <Text size="xs" c="dimmed">
                    {company?.membership ? `${company.membership.role_title}${company.membership.can_sign ? ' · право подписи' : ' · без права подписи'}` : user?.email}
                  </Text>
                </Box>
                <Menu.Divider />
                <Menu.Item leftSection={<IconPlus size={14} />} onClick={() => nav('/companies/connect')}>
                  Подключить компанию по ИНН
                </Menu.Item>
                <Menu.Item leftSection={<IconLogout size={14} />} color="signal" onClick={logout}>
                  Выйти
                </Menu.Item>
              </Menu.Dropdown>
            </Menu>
          </Group>
        </Group>
      </AppShell.Header>
      <Drawer opened={drawer} onClose={close} size="xs" title={<Logo />}>
        <Stack gap={4}>
          <NavItems onClick={close} />
          {companies.length > 1 && (
            <Select
              mt="md"
              label="Компания"
              data={companies.map((c) => ({ value: c.id, label: c.short_name }))}
              value={company?.id ?? null}
              onChange={(v) => v && selectCompany(v)}
              allowDeselect={false}
            />
          )}
        </Stack>
      </Drawer>
      <AppShell.Main>
        <Container size="lg" px={0} pb={90}>
          <Outlet />
        </Container>
      </AppShell.Main>
      <Assistant />
    </AppShell>
  );
}
