create table if not exists hui_group (
  id serial primary key,
  code text unique not null,
  name text not null,
  owner_tg_id bigint not null,
  cycle_total int not null,
  cycle_index int not null default 0,
  stake_amount numeric(18,2) not null,
  created_at timestamptz default now()
);

create table if not exists hui_user (
  id serial primary key,
  tg_id bigint unique not null,
  tg_username text,
  display_name text
);

create table if not exists hui_membership (
  group_id int references hui_group(id) on delete cascade,
  user_id  int references hui_user(id) on delete cascade,
  role text not null default 'member',
  joined_at timestamptz default now(),
  primary key (group_id, user_id)
);

create table if not exists hui_cycle (
  id serial primary key,
  group_id int references hui_group(id) on delete cascade,
  index int not null,
  closed boolean default false,
  closed_at timestamptz
);

create table if not exists hui_payment (
  id serial primary key,
  group_id int references hui_group(id) on delete cascade,
  cycle_id int references hui_cycle(id) on delete cascade,
  user_id  int references hui_user(id) on delete set null,
  amount numeric(18,2) not null,
  note text,
  paid_at timestamptz default now()
);

create unique index if not exists ux_cycle_group_index on hui_cycle(group_id, index);
