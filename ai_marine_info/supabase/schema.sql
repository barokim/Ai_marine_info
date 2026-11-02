-- Supabase SQL Editor에서 사용자가 실행합니다. 이 파일은 앱이 자동 실행하지 않습니다.
begin;

create table if not exists public.posts (
    id uuid primary key default gen_random_uuid(),
    author_id uuid not null references auth.users(id) on delete cascade,
    author_name text not null check (char_length(btrim(author_name)) between 1 and 50),
    title text not null check (char_length(title) between 1 and 100 and char_length(btrim(title)) > 0),
    content text not null check (char_length(content) between 1 and 5000 and char_length(btrim(content)) > 0),
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);
create index if not exists posts_created_idx on public.posts(created_at desc, id desc);
create index if not exists posts_author_idx on public.posts(author_id);

alter table public.posts enable row level security;
alter table public.posts force row level security;
revoke all on public.posts from public, anon, authenticated;
grant select, insert, delete on public.posts to authenticated;
-- 직접 REST를 호출해도 작성자·생성일·ID를 바꿀 수 없도록 열 권한을 좁힙니다.
grant update (title, content) on public.posts to authenticated;

drop policy if exists posts_read on public.posts;
create policy posts_read on public.posts for select to authenticated using ((select auth.uid()) is not null);
drop policy if exists posts_insert on public.posts;
create policy posts_insert on public.posts for insert to authenticated with check (author_id = (select auth.uid()));
drop policy if exists posts_update on public.posts;
create policy posts_update on public.posts for update to authenticated
    using (author_id = (select auth.uid())) with check (author_id = (select auth.uid()));
drop policy if exists posts_delete on public.posts;
create policy posts_delete on public.posts for delete to authenticated using (author_id = (select auth.uid()));

-- 메타데이터는 사용자가 선택한 표시 이름이며 실명 인증 정보가 아닙니다.
-- SECURITY DEFINER는 트리거가 auth.users의 본인 이름을 읽는 데만 사용합니다.
-- 앱에는 서비스 롤 키나 auth.users 조회 권한을 제공하지 않습니다.
create or replace function public.prepare_marine_post()
returns trigger language plpgsql security definer set search_path = '' as $$
begin
    if tg_op = 'INSERT' then
        if auth.uid() is null or new.author_id is distinct from auth.uid() then
            raise exception '작성 권한이 없습니다.' using errcode = '42501';
        end if;
        select coalesce(nullif(left(btrim(u.raw_user_meta_data ->> 'name'), 50), ''), '회원')
            into new.author_name from auth.users u where u.id = auth.uid();
        new.created_at := now();
    else
        new.author_id := old.author_id;
        new.author_name := old.author_name;
        new.id := old.id;
        new.created_at := old.created_at;
    end if;
    new.updated_at := now();
    return new;
end;
$$;
revoke all on function public.prepare_marine_post() from public, anon, authenticated;
drop trigger if exists prepare_marine_post on public.posts;
create trigger prepare_marine_post before insert or update on public.posts
    for each row execute function public.prepare_marine_post();
commit;
