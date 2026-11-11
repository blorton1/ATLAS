-- Integration assertions for an isolated/local Supabase test database.
-- Run as migration administrator AFTER applying the migration. All fixtures
-- roll back. Do not run concurrently with production owner enrollment.
begin;
insert into auth.users(id,email,email_confirmed_at) values
 ('a71a5000-0000-4000-8000-000000000001','atlas-owner-test@example.invalid',now()),
 ('a71a5000-0000-4000-8000-000000000002','atlas-other-test@example.invalid',now());
insert into atlas_private.workspace_owners(user_id) values
 ('a71a5000-0000-4000-8000-000000000001');

set local role authenticated;
select set_config('request.jwt.claim.sub','a71a5000-0000-4000-8000-000000000001',true);
do $$
declare
  snapshot jsonb := '{"asOf":"2026-11-10","mode":"PUBLIC MARKET INTELLIGENCE","accounts":[],"accountPlans":{"existing":{"version":1,"plan":{"notes":"preserve me"}}},"researchReviews":{},"feed":{"events":[],"runs":[]}}';
  result jsonb;
begin
  result := public.atlas_save_workspace(0,snapshot);
  assert (result->>'version')::bigint = 1, 'initial save version';
  result := public.atlas_save_workspace(1,snapshot || '{"asOf":"2026-11-11"}'::jsonb);
  assert (result->>'version')::bigint = 2, 'CAS increments version';
  assert result#>>'{state,accountPlans,existing,plan,notes}' = 'preserve me', 'existing plan preserved';
  begin
    perform public.atlas_save_workspace(1,snapshot);
    raise exception 'FAIL: stale write accepted';
  exception when serialization_failure then null;
  end;
  begin
    update public.atlas_workspaces set version=99;
    raise exception 'FAIL: direct update allowed';
  exception when insufficient_privilege then null;
  end;
  begin
    perform public.atlas_save_workspace(2,'{}'::jsonb);
    raise exception 'FAIL: invalid snapshot accepted';
  exception when check_violation then null;
  end;
end $$;

select set_config('request.jwt.claim.sub','a71a5000-0000-4000-8000-000000000002',true);
do $$
begin
  assert (select count(*)=0 from public.atlas_workspaces), 'other user cannot read owner workspace';
  begin
    perform public.atlas_save_workspace(0,'{}'::jsonb);
    raise exception 'FAIL: unenrolled user can save';
  exception when insufficient_privilege then null;
  end;
  begin
    insert into public.atlas_workspaces(owner_id,state)
    values ('a71a5000-0000-4000-8000-000000000001','{}'::jsonb);
    raise exception 'FAIL: another owner insert allowed';
  exception when insufficient_privilege then null;
  end;
end $$;

set local role anon;
select set_config('request.jwt.claim.sub','',true);
do $$
begin
  begin
    perform 1 from public.atlas_workspaces;
    raise exception 'FAIL: anonymous read allowed';
  exception when insufficient_privilege then null;
  end;
  begin
    perform public.atlas_save_workspace(0,'{}'::jsonb);
    raise exception 'FAIL: anonymous save allowed';
  exception when insufficient_privilege then null;
  end;
end $$;
reset role;
rollback;
