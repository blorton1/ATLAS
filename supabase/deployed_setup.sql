-- Deployment reference (applied through named Supabase migrations). Not a rerunnable script.
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


begin;
alter table atlas_private.workspace_owners enable row level security;
create table atlas_private.workspace_seed (
 email text primary key, state jsonb not null,
 check(email=lower(email))
);
alter table atlas_private.workspace_seed enable row level security;
revoke all on atlas_private.workspace_seed from public,anon,authenticated;
create or replace function public.atlas_open_workspace()
returns jsonb language plpgsql security definer set search_path='' as $$
declare caller uuid:=auth.uid(); allowed_email text; initial jsonb; saved public.atlas_workspaces%rowtype;
begin
 if caller is null then raise exception using errcode='42501',message='Sign in to your ATLAS pipeline'; end if;
 select lower(u.email) into allowed_email from auth.users u
 where u.id=caller and u.email_confirmed_at is not null and coalesce(u.is_anonymous,false)=false;
 select state into initial from atlas_private.workspace_seed where email=allowed_email;
 if initial is null then raise exception using errcode='42501',message='This account is not authorized for ATLAS'; end if;
 insert into atlas_private.workspace_owners(user_id) values(caller) on conflict do nothing;
 insert into public.atlas_workspaces(owner_id,state) values(caller,initial) on conflict do nothing;
 select * into saved from public.atlas_workspaces where owner_id=caller;
 return jsonb_build_object('version',saved.version,'state',saved.state,'updatedAt',saved.updated_at);
end; $$;
revoke all on function public.atlas_open_workspace() from public,anon;
grant execute on function public.atlas_open_workspace() to authenticated;
commit;
begin;
create extension if not exists pg_net with schema extensions;
create extension if not exists pg_cron;
create table atlas_private.daily_runs (
 run_date date primary key,
 nonce uuid not null unique default gen_random_uuid(),
 expires_at timestamptz not null default now()+interval '10 minutes',
 status text not null default 'queued' check(status in ('queued','running','completed','failed')),
 started_at timestamptz,finished_at timestamptz,result jsonb,error text
);
alter table atlas_private.daily_runs enable row level security;
revoke all on atlas_private.daily_runs from public,anon,authenticated;

create function public.atlas_claim_daily_run(nonce uuid)
returns jsonb language plpgsql security definer set search_path='' as $$
declare job atlas_private.daily_runs%rowtype; workspace jsonb;
begin
 select * into job from atlas_private.daily_runs d where d.nonce=$1 and d.status='queued' and d.expires_at>now() for update;
 if job.run_date is null then return null; end if;
 update atlas_private.daily_runs set status='running',started_at=clock_timestamp() where run_date=job.run_date;
 select w.state into workspace from public.atlas_workspaces w join auth.users u on u.id=w.owner_id where lower(u.email)='brendan.lorton123@gmail.com';
 if workspace is null then select state into workspace from atlas_private.workspace_seed where email='brendan.lorton123@gmail.com'; end if;
 if workspace is null then raise exception 'ATLAS workspace is not provisioned'; end if;
 return jsonb_build_object('runDate',job.run_date,'state',workspace);
end $$;
revoke all on function public.atlas_claim_daily_run(uuid) from public,anon,authenticated;
grant execute on function public.atlas_claim_daily_run(uuid) to service_role;

create function public.atlas_finish_daily_run(run_date date,batch jsonb,error_text text default null)
returns jsonb language plpgsql security definer set search_path='' as $$
declare job atlas_private.daily_runs%rowtype; owner uuid; workspace jsonb; prospect jsonb; account jsonb; candidate_id text; norm text; domain text; inserted int:=0; duplicates int:=0; events jsonb:='[]'::jsonb; sources jsonb:='[]'::jsonb; feed jsonb; log jsonb; final_status text;
begin
 select * into job from atlas_private.daily_runs d where d.run_date=$1 for update;
 if job.status is distinct from 'running' then raise exception 'Daily run was not claimed or already completed'; end if;
 select u.id into owner from auth.users u join public.atlas_workspaces w on w.owner_id=u.id where lower(u.email)='brendan.lorton123@gmail.com';
 if owner is not null then select state into workspace from public.atlas_workspaces where owner_id=owner for update;
 else select state into workspace from atlas_private.workspace_seed where email='brendan.lorton123@gmail.com' for update; end if;
 if workspace is null then raise exception 'ATLAS workspace unavailable'; end if;
 if error_text is null then
  if batch is null or jsonb_typeof(batch->'prospects') is distinct from 'array' or jsonb_array_length(batch->'prospects')>5 then raise exception 'Invalid intake batch'; end if;
  for prospect in select value from jsonb_array_elements(batch->'prospects') loop
   if prospect->>'name' is null or prospect->>'website' !~ '^https://' or prospect->>'sourceUrl' !~ '^https://' then raise exception 'Invalid prospect evidence'; end if;
   norm:=regexp_replace(lower(prospect->>'name'),'[^a-z0-9]','','g');
   domain:=regexp_replace(split_part(lower(prospect->>'website'),'/',3),'^www\.','');
   if exists(select 1 from jsonb_array_elements(workspace->'accounts') a where regexp_replace(lower(a->>'name'),'[^a-z0-9]','','g')=norm or regexp_replace(split_part(lower(a->>'website'),'/',3),'^www\.','')=domain) then duplicates:=duplicates+1;continue;end if;
   candidate_id:='cloud-'||replace(gen_random_uuid()::text,'-','');
   account:=jsonb_build_object('id',candidate_id,'name',prospect->>'name','sector',prospect->>'sector','hq',prospect->>'hq','website',prospect->>'website','motion','Acquire','fundingAmount',null,'fundingDate',null,'contractObligations',null,'ttmRevenue',null,'contractedACV',null,'scenarioAnnualValue',null,'scores',jsonb_build_object('fit',0,'urgency',0,'capacity',0,'access',0,'feasibility',0),'gate','Security review','evidenceStrength',0,'stage','Identified','owner','Unassigned','products','[]'::jsonb,'workflows',null,'buyer',prospect->>'buyerRole','useCases',jsonb_build_array(jsonb_build_object('title',prospect->>'workflow','description','Automated workflow hypothesis awaiting discovery','product','To validate','buyer',prospect->>'buyerRole','kpi','To validate')),'signals','[]'::jsonb,'lastReviewed',null,'notes','','accountThesis',prospect->>'openaiFit','dataMode','PUBLIC','businessNeed',prospect->>'businessNeed','openaiFit',prospect->>'openaiFit','buyerRole',prospect->>'buyerRole','nextStep',prospect->>'nextStep','priority',prospect->>'priority');
   log:=jsonb_build_object('id',replace(gen_random_uuid()::text,'-',''),'accountId',candidate_id,'type',prospect->>'type','title',prospect->>'title','date',prospect->>'sourceDate','publishedAt',prospect->>'sourceDate','source',prospect->>'name'||' company announcement','sourceUrl',prospect->>'sourceUrl','verification','Pending','amount',null,'amountBasis','Not extracted; verify original source','workflow',prospect->>'workflow','collectedAt',clock_timestamp());
   account:=jsonb_set(account,'{signals}',jsonb_build_array(log||jsonb_build_object('evidenceType','Pending','ingestedAt',clock_timestamp())));
   workspace:=jsonb_set(workspace,'{accounts}',(workspace->'accounts')||jsonb_build_array(account));
   workspace:=jsonb_set(workspace,array['researchReviews',candidate_id],jsonb_build_object('version',1,'updatedAt',clock_timestamp(),'review',jsonb_build_object('status','Needs review','latestStage','Unknown','usVerified',false,'sectorVerified',false,'latestStageVerified',false,'stageSource','','usSource',prospect->>'sourceUrl','sectorSource',prospect->>'sourceUrl','checkedOn','','reviewer','','rationale','Automated source-backed sales hypothesis awaiting human review. Location excerpt: '||(prospect->>'locationEvidence'))));
   events:=events||jsonb_build_array(log);sources:=sources||jsonb_build_array(jsonb_build_object('name',prospect->>'name','url',prospect->>'sourceUrl','status','ok','detail','Web-search-cited company source fetched; human review pending'));
   inserted:=inserted+1;
  end loop;
 end if;
 final_status:=case when error_text is not null then 'failed' when jsonb_array_length(coalesce(batch->'rejected','[]'::jsonb))>0 then 'partial' else 'success' end;
 log:=jsonb_build_object('id','cloud-daily-'||$1::text,'kind','cloud_research','runDate',$1,'status',final_status,'inserted',inserted,'duplicates',duplicates,'sources',sources,'rejected',coalesce(batch->'rejected','[]'::jsonb),'error',error_text,'collectedAt',clock_timestamp());
 feed:=workspace->'feed';
 feed:=jsonb_set(feed,'{events}',events||coalesce(feed->'events','[]'::jsonb));
 feed:=jsonb_set(feed,'{runs}',jsonb_build_array(log)||coalesce(feed->'runs','[]'::jsonb));
 if final_status='success' then feed:=jsonb_set(feed,'{lastSuccessfulRun}',to_jsonb($1::text));end if;
 workspace:=jsonb_set(workspace,'{feed}',feed);
 workspace:=jsonb_set(workspace,'{asOf}',to_jsonb($1::text));
 if owner is not null then update public.atlas_workspaces set state=workspace,version=version+1,updated_at=clock_timestamp() where owner_id=owner;
 else update atlas_private.workspace_seed set state=workspace where email='brendan.lorton123@gmail.com';end if;
 update atlas_private.daily_runs set status=case when error_text is null then 'completed' else 'failed' end,finished_at=clock_timestamp(),result=log,error=error_text where daily_runs.run_date=$1;
 return jsonb_build_object('inserted',inserted,'duplicates',duplicates,'status',final_status);
end $$;
revoke all on function public.atlas_finish_daily_run(date,jsonb,text) from public,anon,authenticated;
grant execute on function public.atlas_finish_daily_run(date,jsonb,text) to service_role;

create function atlas_private.enqueue_daily_intake(force_run boolean default false)
returns jsonb language plpgsql security definer set search_path='' as $$
declare local_time timestamp:=now() at time zone 'America/New_York'; job atlas_private.daily_runs%rowtype; request_id bigint;
begin
 if not force_run and extract(hour from local_time)<>7 then return jsonb_build_object('skipped','Not 7 AM Eastern');end if;
 insert into atlas_private.daily_runs(run_date) values(local_time::date) on conflict(run_date) do update set nonce=gen_random_uuid(),expires_at=now()+interval '10 minutes',status='queued',started_at=null,finished_at=null,error=null where force_run and daily_runs.status='failed' returning * into job;
 if job.run_date is null then return jsonb_build_object('skipped','Already queued for this Eastern date');end if;
 select net.http_post(url:='https://iikworeqzzinccrhshed.supabase.co/functions/v1/atlas-daily-intake',body:=jsonb_build_object('nonce',job.nonce),headers:='{"Content-Type":"application/json"}'::jsonb,timeout_milliseconds:=180000) into request_id;
 return jsonb_build_object('runDate',job.run_date,'requestId',request_id);
end $$;
revoke all on function atlas_private.enqueue_daily_intake(boolean) from public,anon,authenticated;
commit;


