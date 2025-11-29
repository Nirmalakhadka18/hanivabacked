-- Supabase table for transaction history
create table transactions (
  id uuid primary key default gen_random_uuid(),
  tx_id text,
  from_address text,
  to_address text,
  amount_lovelace bigint,
  metadata jsonb,
  ipfs_cid text,
  created_at timestamptz default now()
);
