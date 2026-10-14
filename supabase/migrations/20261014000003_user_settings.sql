-- SPDX-License-Identifier: GPL-3.0-or-later
-- Grimoire Linux accounts, part 3: each account's settings backup (the same .grimoire-backup zip as a file,
-- base64), one row per account, readable and writable only by that account.

create table public.user_settings (
  user_id uuid primary key default auth.uid() references auth.users (id) on delete cascade,
  data text not null
    constraint data_base64 check (data ~ '^[A-Za-z0-9+/]*={0,2}$')
    constraint data_size check (octet_length(data) <= 1500000),        -- a 1 MB zip, base64-encoded
  updated_at timestamptz not null default now()
);
comment on table public.user_settings is 'Grimoire Linux: settings backup per account (checked again by the app).';

alter table public.user_settings enable row level security;
revoke all on public.user_settings from anon, authenticated;
grant select, insert, update, delete on public.user_settings to authenticated;

create policy "user_settings: owner reads" on public.user_settings
  for select to authenticated using ((select auth.uid()) = user_id);
create policy "user_settings: owner inserts" on public.user_settings
  for insert to authenticated with check ((select auth.uid()) = user_id);
create policy "user_settings: owner updates" on public.user_settings
  for update to authenticated using ((select auth.uid()) = user_id) with check ((select auth.uid()) = user_id);
create policy "user_settings: owner deletes" on public.user_settings
  for delete to authenticated using ((select auth.uid()) = user_id);

create or replace function private.touch_updated_at()
returns trigger
language plpgsql
set search_path = ''
as $$
begin
  new.updated_at := now();
  return new;
end;
$$;
revoke all on function private.touch_updated_at() from public, anon, authenticated;

create trigger user_settings_updated_at
  before update on public.user_settings
  for each row execute function private.touch_updated_at();
