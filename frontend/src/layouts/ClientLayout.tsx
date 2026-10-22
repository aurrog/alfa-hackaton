import { Avatar, Box, Button, Container, Group, Menu, Text, UnstyledButton } from '@mantine/core';
import { IconBuildingStore, IconCheck, IconChevronDown, IconCreditCard, IconFileText, IconHome2, IconLogout, IconMessageCircle, IconPlus } from '@tabler/icons-react';
import { useState } from 'react';
import { Link, NavLink, Outlet, useLocation, useNavigate } from 'react-router-dom';
import { AssistantButton, AssistantDrawer } from '../components/Assistant';
import { Notifications } from '../components/Notifications';
import { useAuth } from '../auth/AuthContext';

const NAV = [
  { to: '/', label: 'Главная', exact: true },
  { to: '/applications', label: 'Заявки' },
  { to: '/loans', label: 'Кредиты' },
];

export function Logo({ sub, compact }: { sub?: string; compact?: boolean }) {
  return (
    <Group gap={10} wrap="nowrap">
      <span className="logo-mark" aria-hidden>
        <svg width="18" height="18" viewBox="0 0 18 18">
          <rect x="2" y="10" width="3.2" height="6" rx="1" fill="#fff" />
          <rect x="7.4" y="6.5" width="3.2" height="9.5" rx="1" fill="#fff" />
          <rect x="12.8" y="2" width="3.2" height="14" rx="1" fill="#fff" />
        </svg>
      </span>
      {!compact && (
        <Box lh={1.15}>
          <Text fw={700} className="display" fz={15}>
            Кредитный кабинет
          </Text>
          <Text fz={11.5} c="dimmed">
            {sub ?? 'для предпринимателей'}
          </Text>
        </Box>
      )}
    </Group>
  );
}

function isActive(path: string, to: string, exact?: boolean) {
  return exact ? path === to : path.startsWith(to);
}

export function ClientLayout() {
  const { user, companies, company, selectCompany, logout } = useAuth();
  const [assistant, setAssistant] = useState(false);
  const nav = useNavigate();
  const loc = useLocation();
  const initials = user?.full_name.split(' ').slice(0, 2).map((s) => s[0]).join('');
  const newActive = loc.pathname.startsWith('/products');

  return (
    <Box mih="100vh">
      <Box component="header" className="topbar" pos="sticky" top={0} style={{ zIndex: 120 }}>
        <Container size={1160} px={{ base: 16, sm: 24 }} h="100%">
          <Group h="100%" justify="space-between" wrap="nowrap" gap="lg">
            <Group gap={28} wrap="nowrap" h="100%">
              <UnstyledButton onClick={() => nav('/')} aria-label="На главную">
                <Logo />
              </UnstyledButton>
              <nav className="topnav" aria-label="Разделы">
                <Box visibleFrom="md" style={{ display: 'contents' }}>
                  {NAV.map((n) => (
                    <NavLink key={n.to} to={n.to} className={isActive(loc.pathname, n.to, n.exact) ? 'active' : undefined} end={n.exact}>
                      {n.label}
                    </NavLink>
                  ))}
                </Box>
              </nav>
            </Group>
            <Group gap={6} wrap="nowrap">
              <Button visibleFrom="md" size="sm" leftSection={<IconPlus size={16} />} component={Link} to="/products" variant={newActive ? 'default' : 'filled'} mr={8}>
                Новая заявка
              </Button>
              {company && (
                <Menu position="bottom-end" width={300}>
                  <Menu.Target>
                    <UnstyledButton visibleFrom="sm" px={10} py={6} style={{ borderRadius: 10 }}>
                      <Group gap={6} wrap="nowrap">
                        <IconBuildingStore size={16} color="var(--muted)" />
                        <Text size="sm" fw={500} maw={200} truncate>
                          {company.short_name}
                        </Text>
                        <IconChevronDown size={14} color="var(--muted)" />
                      </Group>
                    </UnstyledButton>
                  </Menu.Target>
                  <Menu.Dropdown>
                    <Menu.Label>Компании</Menu.Label>
                    {companies.map((c) => (
                      <Menu.Item key={c.id} onClick={() => selectCompany(c.id)} rightSection={c.id === company.id ? <IconCheck size={14} /> : null}>
                        <Text size="sm" fw={500}>
                          {c.short_name}
                        </Text>
                        <Text size="xs" c="dimmed">
                          ИНН {c.inn}
                        </Text>
                      </Menu.Item>
                    ))}
                    <Menu.Divider />
                    <Menu.Item leftSection={<IconPlus size={14} />} onClick={() => nav('/companies/connect')}>
                      Подключить компанию по ИНН
                    </Menu.Item>
                  </Menu.Dropdown>
                </Menu>
              )}
              <Notifications />
              <Menu position="bottom-end" width={280}>
                <Menu.Target>
                  <UnstyledButton aria-label="Профиль">
                    <Avatar size={34} radius="xl" color="ink" variant="light">
                      {initials}
                    </Avatar>
                  </UnstyledButton>
                </Menu.Target>
                <Menu.Dropdown>
                  <Box px="sm" py={8}>
                    <Text size="sm" fw={600}>
                      {user?.full_name}
                    </Text>
                    <Text size="xs" c="dimmed">
                      {company?.membership ? `${company.membership.role_title} · ${company.membership.can_sign ? 'право подписи' : 'без права подписи'}` : user?.email}
                    </Text>
                  </Box>
                  {companies.length > 1 && (
                    <Box hiddenFrom="sm">
                      <Menu.Divider />
                      <Menu.Label>Компания</Menu.Label>
                      {companies.map((c) => (
                        <Menu.Item key={c.id} onClick={() => selectCompany(c.id)} rightSection={c.id === company?.id ? <IconCheck size={14} /> : null}>
                          {c.short_name}
                        </Menu.Item>
                      ))}
                    </Box>
                  )}
                  <Menu.Divider />
                  <Menu.Item leftSection={<IconPlus size={14} />} onClick={() => nav('/companies/connect')}>
                    Подключить компанию по ИНН
                  </Menu.Item>
                  <Menu.Item leftSection={<IconLogout size={14} />} color="bad" onClick={logout}>
                    Выйти
                  </Menu.Item>
                </Menu.Dropdown>
              </Menu>
            </Group>
          </Group>
        </Container>
      </Box>

      <Container size={1160} px={{ base: 16, sm: 24 }} pt={{ base: 24, sm: 36 }} pb={{ base: 110, md: 96 }}>
        <div key={loc.pathname} className="page-fade">
          <Outlet />
        </div>
      </Container>

      <nav className="tabbar" aria-label="Разделы">
        <NavLink to="/" end className={loc.pathname === '/' ? 'active' : undefined}>
          <IconHome2 size={22} stroke={1.7} />
          Главная
        </NavLink>
        <NavLink to="/applications" className={loc.pathname.startsWith('/applications') ? 'active' : undefined}>
          <IconFileText size={22} stroke={1.7} />
          Заявки
        </NavLink>
        <NavLink to="/products" className={`new${newActive ? ' active' : ''}`}>
          <span className="plus">
            <IconPlus size={20} stroke={2.2} />
          </span>
        </NavLink>
        <NavLink to="/loans" className={loc.pathname.startsWith('/loans') ? 'active' : undefined}>
          <IconCreditCard size={22} stroke={1.7} />
          Кредиты
        </NavLink>
        <button type="button" onClick={() => setAssistant(true)}>
          <IconMessageCircle size={22} stroke={1.7} />
          Помощник
        </button>
      </nav>
      <AssistantButton onClick={() => setAssistant(true)} />
      <AssistantDrawer opened={assistant} onClose={() => setAssistant(false)} />
    </Box>
  );
}
