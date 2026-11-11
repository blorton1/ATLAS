-- Owner-private ATLAS workspace. Apply as the Supabase migration administrator.
-- No browser secret/service-role key is required. The public interview demo
-- continues to use its independent, visitor-local snapshot.
begin;

create schema if not exists atlas_private;
revoke all on schema atlas_private from public, anon, authenticated;

create table if not exists atlas_private.workspace_owners (
  user_id uuid primary key references auth.users(id) on delete cascade,
  enrolled_at timestamptz not null default now()
);
revoke all on atlas_private.workspace_owners from public, anon, authenticated;

-- Enrollment is an administrator action after the owner signs in and confirms
-- their email. Run separately after reviewing the matching auth.users row:
-- insert into atlas_private.workspace_owners(user_id)
-- select id from auth.users
-- where lower(email) in ('brendan.lorton123@gmail.com',
--                         'blorton@wharton.upenn.edu')
--   and email_confirmed_at is not null
-- on conflict do nothing;
-- Do not derive ownership from raw_user_meta_data or browser-supplied email.

create or replace function public.atlas_is_workspace_owner()
returns boolean language sql stable security definer
set search_path = ''
as $$
  select auth.uid() is not null and exists (
    select 1 from atlas_private.workspace_owners where user_id = auth.uid()
  );
$$;
revoke all on function public.atlas_is_workspace_owner() from public, anon;
grant execute on function public.atlas_is_workspace_owner() to authenticated;

create table if not exists public.atlas_workspaces (
  owner_id uuid primary key references auth.users(id) on delete cascade,
  version bigint not null default 1 check (version >= 1),
  state jsonb not null,
  updated_at timestamptz not null default now(),
  constraint atlas_workspace_shape check (
    jsonb_typeof(state) = 'object'
    and state ?& array['asOf','mode','accounts','accountPlans','researchReviews','feed']
    and jsonb_typeof(state->'asOf') = 'string'
    and jsonb_typeof(state->'mode') = 'string'
    and jsonb_typeof(state->'accounts') = 'array'
    and jsonb_typeof(state->'accountPlans') = 'object'
    and jsonb_typeof(state->'researchReviews') = 'object'
    and jsonb_typeof(state->'feed') = 'object'
    and octet_length(state::text) <= 5242880
  )
);
alter table public.atlas_workspaces enable row level security;
alter table public.atlas_workspaces force row level security;
revoke all on public.atlas_workspaces from public, anon, authenticated;
grant select, insert on public.atlas_workspaces to authenticated;

create policy atlas_owner_read on public.atlas_workspaces for select to authenticated
  using (owner_id = (select auth.uid()) and (select public.atlas_is_workspace_owner()));
create policy atlas_owner_initialize on public.atlas_workspaces for insert to authenticated
  with check (owner_id = (select auth.uid()) and version = 1
              and (select public.atlas_is_workspace_owner()));
-- No UPDATE or DELETE grant/policy: browser updates must use the CAS RPC.

create or replace function public.atlas_save_workspace(
  expected_version bigint,
  new_state jsonb
)
returns jsonb language plpgsql security definer
set search_path = ''
as $$
declare
  caller uuid := auth.uid();
  saved public.atlas_workspaces%rowtype;
begin
  if caller is null or not public.atlas_is_workspace_owner() then
    raise exception using errcode = '42501', message = 'ATLAS owner access required';
  end if;
  if expected_version is null or expected_version < 0 then
    raise exception using errcode = '22023', message = 'Expected version must be nonnegative';
  end if;
  if new_state is null then
    raise exception using errcode = '22023', message = 'Workspace state is required';
  end if;
  if expected_version = 0 then
    insert into public.atlas_workspaces(owner_id, version, state, updated_at)
      values (caller, 1, new_state, clock_timestamp())
      on conflict (owner_id) do nothing
      returning * into saved;
  else
    update public.atlas_workspaces
      set state = new_state, version = version + 1, updated_at = clock_timestamp()
      where owner_id = caller and version = expected_version
      returning * into saved;
  end if;
  if saved.owner_id is null then
    -- A stale tab must reload, merge, and explicitly retry; never overwrite.
    raise exception using errcode = '40001', message = 'Workspace version conflict; reload before saving';
  end if;
  return jsonb_build_object('version',saved.version,'state',saved.state,'updatedAt',saved.updated_at);
end;
$$;
revoke all on function public.atlas_save_workspace(bigint,jsonb) from public, anon;
grant execute on function public.atlas_save_workspace(bigint,jsonb) to authenticated;

comment on table public.atlas_workspaces is
  'Private ATLAS snapshot per enrolled owner; CAS prevents cross-device lost updates.';
commit;
