import ChangeAdminPassword from '@/components/settings/ChangeAdminPassword.vue'
import DatabaseConfigurations from '@/components/settings/DatabaseConfigurations.vue'
import DatabaseQuickActions from '@/components/settings/DatabaseQuickActions.vue'
import Firewall from '@/components/settings/Firewall.vue'
import Git from '@/components/settings/Git.vue'
import LLM from '@/components/settings/LLM.vue'
import Mail from '@/components/settings/Mail.vue'
import Notifications from '@/components/settings/Notifications.vue'
import S3Bucket from '@/components/settings/S3Bucket.vue'
import SshKeys from '@/components/settings/SshKeys.vue'
import TwoFactor from '@/components/settings/TwoFactor.vue'
import Waf from '@/components/settings/Waf.vue'
import Workers from '@/components/settings/Workers.vue'

// Single source of truth for id/label/component so SettingsDialog can resolve
// a routed subsection id without each page owning its own private mapping.
export const GENERAL_SECTIONS = [
  {
    id: 'github',
    label: 'Git settings',
    description: 'Connect GitHub for private installs and repo browsing.',
    component: Git,
  },
  {
    id: 's3-bucket',
    label: 'Object storage settings',
    description: 'Connect S3-compatible storage for offsite backups.',
    component: S3Bucket,
  },
  {
    id: 'llm',
    label: 'AI assistant settings',
    description: 'Connect an LLM provider to power assistant features.',
    component: LLM,
  },
  {
    id: 'notifications',
    label: 'Notification settings',
    description: 'Alert when host resource usage crosses a limit.',
    component: Notifications,
  },
  {
    id: 'mail',
    label: 'Mail settings',
    description: 'Send alerts to a mailbox alongside Central and webhooks.',
    component: Mail,
  },
  {
    id: 'workers',
    label: 'Background workers',
    description: 'Configure background worker groups and queues.',
    component: Workers,
  },
]

export const DATABASE_SECTIONS = [
  {
    id: 'configurations',
    label: 'Database configurations',
    description: 'Inspect MariaDB system variables and tune guarded dynamic settings.',
    component: DatabaseConfigurations,
  },
  {
    id: 'quick-actions',
    label: 'Quick actions',
    component: DatabaseQuickActions,
  },
]

export const SECURITY_SECTIONS = [
  {
    id: 'password',
    label: 'Change password',
    description: 'Update the password that signs in to this bench.',
    component: ChangeAdminPassword,
  },
  {
    id: 'two-factor',
    label: 'Two-factor authentication',
    description: 'Require a code from an enrolled device at every sign-in.',
    component: TwoFactor,
  },
  {
    id: 'firewall',
    label: 'Firewall settings',
    description: 'Restrict server access with IP allow and block rules.',
    component: Firewall,
  },
  {
    id: 'waf',
    label: 'Web application firewall',
    description: 'Inspect incoming requests for attacks before they reach your sites.',
    component: Waf,
  },
  {
    id: 'ssh-keys',
    label: 'SSH keys',
    description: 'Manage authorized public keys for server access.',
    component: SshKeys,
  },
]
