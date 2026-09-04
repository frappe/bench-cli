import { sitesApi } from '@/api/sites'

/** Uploads picked backup archives and returns the staged upload id. */
export const uploadBackupFiles = async (files) => {
  const form = new FormData()
  for (const key of ['database', 'public_files', 'private_files']) {
    if (files[key]) form.append(key, files[key], files[key].name)
  }
  const result = await sitesApi.uploadBackup(form)
  if (!result?.upload_id) {
    throw new Error(result?.error?.message || 'Could not upload the backup files.')
  }
  return result.upload_id
}

export const validateBackupFiles = (files) => {
  if (!files.database) return 'A database backup file is required.'
  return null
}
