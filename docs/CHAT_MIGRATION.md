# Direct conversation migration runbook

The chat schema migration merges per-listing conversations into the oldest conversation for each participant pair. It
preserves message order and read timestamps, repoints escrow offers and conversation-targeted notifications, and copies
every old order association into the conversation's `orders` relation before removing duplicate conversations.
Migration `0007` encrypts existing message bodies at rest. The server still decrypts them for API responses; this is not
end-to-end encryption. Attachments are not encrypted by this migration.

Do not run this against production until a recent database backup exists and the dry-run report has been reviewed.
Pause writes that create messages or conversations during the merge window. Before deploying code that writes encrypted
bodies, configure `CHAT_MESSAGE_ENCRYPTION_KEYS` on Vercel and every realtime/Django host. Generate a Fernet key with
`python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"` and keep it outside source
control. The same key value is required by every process that reads or writes the shared database.

1. Apply the additive schema expansion:

   ```powershell
   .\venv\Scripts\python.exe manage.py migrate chat 0005 --settings=config.settings.prod
   ```

2. Print the planned merge report. This command does not mutate data:

   ```powershell
   .\venv\Scripts\python.exe manage.py merge_direct_conversations --dry-run --settings=config.settings.prod
   ```

3. Review the counts and duplicate IDs against the backup and production data. Only after approval, apply the merge:

   ```powershell
   .\venv\Scripts\python.exe manage.py merge_direct_conversations --apply --settings=config.settings.prod
   ```

4. Apply the remaining migrations:

   ```powershell
   .\venv\Scripts\python.exe manage.py migrate --settings=config.settings.prod
   ```

The final migration reruns the merge idempotently and then adds canonical-pair uniqueness and the distinct-participant
check constraint. Migration `0007` then encrypts legacy plaintext message bodies; it is idempotent if interrupted and
rerun. It fails if the encryption key is missing or invalid. It fails instead of installing constraints on unmerged
rows. Do not remove the backup until messages, offers, and all previously linked orders have been spot-checked.
