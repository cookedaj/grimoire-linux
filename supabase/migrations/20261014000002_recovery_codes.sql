-- SPDX-License-Identifier: GPL-3.0-or-later
-- Grimoire Linux accounts, part 2: one-time recovery codes for username accounts (they have no real email).
--
-- A code is 80 random bits shown once in the app (XXXXX-XXXXX-XXXXX-XXXXX, hex). Only its bcrypt hash is stored,
-- in a table the API can't reach. recover_account() checks it, sets the new password, signs the account out
-- everywhere and returns a fresh code (the old one is spent). Wrong codes lock that username for a while:
-- 5 failures → 30 s, doubling, at most 15 minutes, counted for unknown usernames too so the answer doesn't
-- reveal whether a username exists.

create table private.recovery_codes (
  user_id uuid primary key references auth.users (id) on delete cascade,
  code_hash text not null,
  created_at timestamptz not null default now()
);

create table private.recovery_attempts (
  username extensions.citext primary key,
  failures int not null default 0,
  locked_until timestamptz,
  updated_at timestamptz not null default now()
);

create or replace function private.format_code(raw text)
returns text
language sql
immutable
set search_path = ''
as $$
  select substr(raw, 1, 5) || '-' || substr(raw, 6, 5) || '-' || substr(raw, 11, 5) || '-' || substr(raw, 16, 5);
$$;

-- Called by the app right after sign-up, and from Settings → Account → New recovery code.
create or replace function public.issue_recovery_code()
returns text
language plpgsql
security definer
set search_path = ''
as $$
declare
  uid uuid := auth.uid();
  raw text;
begin
  if uid is null then
    raise exception 'sign in first' using errcode = '42501';
  end if;
  if not exists (select 1 from auth.users u where u.id = uid and lower(u.email) like '%@users.grimoire.invalid') then
    raise exception 'recovery codes are for username accounts' using errcode = '42501';
  end if;
  raw := upper(encode(extensions.gen_random_bytes(10), 'hex'));
  insert into private.recovery_codes (user_id, code_hash)
    values (uid, extensions.crypt(raw, extensions.gen_salt('bf', 10)))
    on conflict (user_id) do update set code_hash = excluded.code_hash, created_at = now();
  return private.format_code(raw);
end;
$$;

create or replace function public.recover_account(p_username text, p_code text, p_new_password text)
returns jsonb
language plpgsql
security definer
set search_path = ''
as $$
declare
  uname extensions.citext := left(coalesce(p_username, ''), 32);
  code text := upper(regexp_replace(coalesce(p_code, ''), '[^0-9A-Fa-f]', '', 'g'));
  locked timestamptz;
  uid uuid;
  hash text;
  raw text;
begin
  if p_new_password is null or length(p_new_password) < 10 or octet_length(p_new_password) > 72 then
    return jsonb_build_object('ok', false, 'error', 'weak_password');
  end if;
  -- a name that can't be a username or a code of the wrong length is refused before any row is written, so
  -- anonymous callers can't fill recovery_attempts with junk (the rules are public, so this reveals nothing)
  if uname::text !~ '^[A-Za-z0-9][A-Za-z0-9_-]{2,31}$' or length(code) <> 20 then
    return jsonb_build_object('ok', false, 'error', 'invalid');
  end if;
  delete from private.recovery_attempts a                        -- housekeeping: forget old, unlocked names
   where a.username in (select o.username from private.recovery_attempts o
                         where o.updated_at < now() - interval '1 day'
                           and (o.locked_until is null or o.locked_until < now()) and o.username <> uname
                         limit 100 for update skip locked);
  insert into private.recovery_attempts (username) values (uname) on conflict (username) do nothing;
  select a.locked_until into locked from private.recovery_attempts a where a.username = uname for update;
  if locked is not null and locked > now() then
    return jsonb_build_object('ok', false, 'error', 'locked',
                              'retry_after', ceil(extract(epoch from locked - now()))::int);
  end if;
  select p.id into uid from public.profiles p where p.username = uname;
  select c.code_hash into hash from private.recovery_codes c where c.user_id = uid;
  -- always one bcrypt, so an unknown username takes as long as a wrong code
  if extensions.crypt(code, coalesce(hash, extensions.gen_salt('bf', 10))) is distinct from hash
     or uid is null then
    update private.recovery_attempts a
       set failures = a.failures + 1,
           updated_at = now(),
           locked_until = case when a.failures + 1 >= 5
                               then now() + least(interval '15 minutes',
                                                  interval '30 seconds' * power(2, a.failures + 1 - 5))
                          end
     where a.username = uname;
    return jsonb_build_object('ok', false, 'error', 'invalid');
  end if;
  -- Supabase Auth stores bcrypt hashes; pgcrypto's bf hashes are the same format
  update auth.users set encrypted_password = extensions.crypt(p_new_password, extensions.gen_salt('bf', 10)),
                        updated_at = now()
   where id = uid;
  delete from auth.sessions where user_id = uid;                  -- signed out everywhere
  delete from auth.refresh_tokens where user_id = uid::text;
  raw := upper(encode(extensions.gen_random_bytes(10), 'hex'));
  update private.recovery_codes set code_hash = extensions.crypt(raw, extensions.gen_salt('bf', 10)), created_at = now()
   where user_id = uid;
  delete from private.recovery_attempts a where a.username = uname;
  return jsonb_build_object('ok', true, 'code', private.format_code(raw));
end;
$$;

-- Postgres lets everyone execute new functions, and Supabase adds anon/authenticated by default: narrow it.
revoke all on function private.format_code(text) from public, anon, authenticated;
revoke all on function public.issue_recovery_code() from public, anon, authenticated;
grant execute on function public.issue_recovery_code() to authenticated;
revoke all on function public.recover_account(text, text, text) from public, anon, authenticated;
grant execute on function public.recover_account(text, text, text) to anon, authenticated;
revoke all on function private.handle_new_user() from public, anon, authenticated;
revoke all on function private.guard_login_address() from public, anon, authenticated;
