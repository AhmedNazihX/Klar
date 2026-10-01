-- Lock order for the storage budget (story P3b, decision 027).
--
-- private.track_storage() runs after each row, so it takes the user's storage_usage row lock only
-- after the row's own lock and the foreign-key checks' KEY SHARE locks on its parents. Two sessions
-- of one user could then deadlock (40P01): delete_my_data locks storage_usage while deleting the
-- answers and then needs the systems rows, while an insert of a classification holds KEY SHARE on
-- its system and waits for storage_usage.
--
-- The fix: before each statement on the four tables, the caller's storage_usage row is locked
-- first, before any row is touched, so every writer takes the locks in the same order: storage_usage,
-- then rows and parents. The size check stays in track_storage(), after the row (the lock is already
-- held, so it doesn't wait there). Statement triggers also fire for the cascaded deletes inside a
-- statement; the lock is then already held. Without a session (auth.uid() null, as in the pg_cron
-- cleanup) nothing is locked here: those writes are the server's own.
create function private.lock_storage()
returns trigger
language plpgsql
security definer
set search_path = ''
as $$
declare
  uid uuid := auth.uid();
begin
  if uid is null then
    return null;
  end if;
  if tg_op = 'DELETE' then
    -- Never insert on a delete: a cascade from a deleted auth user must not re-create the total.
    perform from private.storage_usage where user_id = uid for update;
  else
    -- Creates the total on the user's first write, and locks it either way.
    insert into private.storage_usage as u (user_id) values (uid)
    on conflict (user_id) do update set bytes = u.bytes;
  end if;
  return null;
end
$$;

revoke execute on function private.lock_storage() from public, anon, authenticated;

create trigger inventories_lock_storage before insert or update or delete on public.inventories
  for each statement execute function private.lock_storage();
create trigger systems_lock_storage before insert or update or delete on public.systems
  for each statement execute function private.lock_storage();
create trigger classifications_lock_storage before insert or update or delete
  on public.classifications
  for each statement execute function private.lock_storage();
create trigger interview_answers_lock_storage before insert or update or delete
  on public.interview_answers
  for each statement execute function private.lock_storage();
