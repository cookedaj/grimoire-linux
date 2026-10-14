-- SPDX-License-Identifier: GPL-3.0-or-later
-- Grimoire Linux accounts, part 1: one profile row per account (username, optional private email).
--
-- Username accounts sign in to Supabase Auth with a made-up address <lowercase username>@users.grimoire.invalid
-- (grimoire/supabase_app.py SYNTHETIC_DOMAIN; change both places together). The username is the only thing a
-- person types; nothing here ever turns a username into an email address.

create extension if not exists citext with schema extensions;
create extension if not exists pgcrypto with schema extensions;

-- Functions and tables nobody should reach through the API live in "private" (not exposed by PostgREST).
create schema if not exists private;
revoke all on schema private from public, anon, authenticated;

create table public.profiles (
  id uuid primary key references auth.users (id) on delete cascade,
  username extensions.citext not null unique
    constraint username_format check (username::text ~ '^[A-Za-z0-9][A-Za-z0-9_-]{2,31}$'),
  email text
    constraint email_format check (email is null or (length(email) <= 254 and email ~ '^[^@[:space:]]+@[^@[:space:]]+\.[^@[:space:]]+$')),
  created_at timestamptz not null default now()
);
comment on table public.profiles is 'Grimoire Linux: username and optional contact email (only its owner can read it).';

alter table public.profiles enable row level security;
revoke all on public.profiles from anon, authenticated;
grant select on public.profiles to authenticated;
grant update (email) on public.profiles to authenticated;          -- the username is fixed (it is the login)

create policy "profiles: owner reads" on public.profiles
  for select to authenticated using ((select auth.uid()) = id);
create policy "profiles: owner updates email" on public.profiles
  for update to authenticated using ((select auth.uid()) = id) with check ((select auth.uid()) = id);

-- A new auth user gets its profile row. Username sign-ups must use exactly their own synthetic address; anything
-- else under that domain is refused, so nobody can sign up "bob" with alice's login address. OAuth accounts
-- (Google, GitHub) get a username derived from the provider, made unique with a number.
create or replace function private.handle_new_user()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
declare
  meta jsonb := coalesce(new.raw_user_meta_data, '{}'::jsonb);
  domain constant text := 'users.grimoire.invalid';
  wanted text := meta ->> 'username';
  contact text := nullif(meta ->> 'contact_email', '');
  base text;
  candidate text;
  n int := 1;
begin
  if lower(coalesce(new.email, '')) like '%@' || domain then
    if wanted is null or lower(new.email) <> lower(wanted) || '@' || domain then
      raise exception 'username accounts must sign up with their own login address' using errcode = '23514';
    end if;
    -- the CHECK and UNIQUE constraints refuse a bad or taken username, which fails the whole sign-up
    insert into public.profiles (id, username, email) values (new.id, wanted, contact);
    return new;
  end if;
  base := regexp_replace(coalesce(meta ->> 'user_name', meta ->> 'preferred_username',
                                  split_part(coalesce(new.email, ''), '@', 1), ''), '[^A-Za-z0-9_-]', '', 'g');
  base := left(base, 28);
  if length(base) < 3 or base !~ '^[A-Za-z0-9]' then
    base := 'user' || left(replace(new.id::text, '-', ''), 8);
  end if;
  candidate := base;
  while exists (select 1 from public.profiles p where p.username = candidate::extensions.citext) loop
    n := n + 1;
    candidate := base || n::text;
  end loop;
  insert into public.profiles (id, username) values (new.id, candidate);
  return new;
end;
$$;

create trigger on_auth_user_created
  after insert on auth.users
  for each row execute function private.handle_new_user();

-- Login addresses under the synthetic domain never change: changing one would let an account take over
-- another username's sign-in.
create or replace function private.guard_login_address()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
declare
  domain constant text := 'users.grimoire.invalid';
begin
  if (lower(coalesce(old.email, '')) like '%@' || domain or lower(coalesce(new.email, '')) like '%@' || domain
      or lower(coalesce(new.email_change, '')) like '%@' || domain)
     and (new.email is distinct from old.email or coalesce(new.email_change, '') <> '') then
    raise exception 'Grimoire usernames can''t change their login address' using errcode = '42501';
  end if;
  return new;
end;
$$;

create trigger guard_login_address
  before update of email, email_change on auth.users
  for each row execute function private.guard_login_address();
