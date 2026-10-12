create table if not exists users(
    id SERIAL primary key,
    username varchar(50) unique not null,
    email varchar(100) unique not null,
    password_hash varchar(255) unique not null,
    phone varchar(20),
    is_vertified boolean default false,
    create_at timestamp default current_timestamp
)