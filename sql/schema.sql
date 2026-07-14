-- ============================================================
-- Esquema de base de datos - Sistema de Timesheets CORPEI
-- Ejecutar en el SQL Editor de Supabase (Project > SQL Editor)
-- ============================================================

-- Extensión para generar UUIDs
create extension if not exists "pgcrypto";

-- Tipo enumerado de roles (RF-08)
do $$ begin
    create type rol_usuario as enum (
        'consultor',
        'coordinador',
        'finanzas',
        'contabilidad',
        'presidencia'
    );
exception
    when duplicate_object then null;
end $$;

-- Estados posibles de un timesheet (RF-02, RF-04)
do $$ begin
    create type estado_timesheet as enum (
        'borrador',
        'enviado',
        'aprobado',
        'rechazado',
        'correccion_solicitada'
    );
exception
    when duplicate_object then null;
end $$;

-- Tipo de evento en el historial (RF-05)
do $$ begin
    create type tipo_evento_historial as enum (
        'creado',
        'editado',
        'enviado',
        'aprobado',
        'rechazado',
        'correccion_solicitada',
        'comentario'
    );
exception
    when duplicate_object then null;
end $$;

-- ------------------------------------------------------------
-- Usuarios (autenticación propia, no Supabase Auth)
-- ------------------------------------------------------------
create table if not exists usuarios (
    id uuid primary key default gen_random_uuid(),
    nombre_completo text not null,
    email text not null unique,
    password_hash text not null,
    rol rol_usuario not null default 'consultor',
    activo boolean not null default true,
    creado_en timestamptz not null default now()
);

-- ------------------------------------------------------------
-- Centros de costo (RF-09, RF-15)
-- ------------------------------------------------------------
create table if not exists centros_costo (
    id uuid primary key default gen_random_uuid(),
    codigo text not null unique,
    nombre text not null,
    activo boolean not null default true,
    creado_en timestamptz not null default now()
);

-- ------------------------------------------------------------
-- Proyectos (RF-09, RF-15)
-- ------------------------------------------------------------
create table if not exists proyectos (
    id uuid primary key default gen_random_uuid(),
    codigo text not null unique,
    nombre text not null,
    centro_costo_id uuid references centros_costo(id),
    coordinador_id uuid references usuarios(id),
    presupuesto_asignado numeric(14, 2),
    activo boolean not null default true,
    creado_en timestamptz not null default now()
);

-- Relación consultor <-> proyecto (un consultor puede estar en varios proyectos)
create table if not exists proyecto_consultores (
    proyecto_id uuid not null references proyectos(id) on delete cascade,
    consultor_id uuid not null references usuarios(id) on delete cascade,
    primary key (proyecto_id, consultor_id)
);

-- ------------------------------------------------------------
-- Timesheets (cabecera) - RF-01, RF-02, RF-09
-- ------------------------------------------------------------
create table if not exists timesheets (
    id uuid primary key default gen_random_uuid(),
    consultor_id uuid not null references usuarios(id),
    proyecto_id uuid not null references proyectos(id),
    centro_costo_id uuid not null references centros_costo(id),
    periodo text not null,              -- ej: '2026-07'
    estado estado_timesheet not null default 'borrador',
    version integer not null default 1,  -- RF-11 trazabilidad de versiones
    total_horas numeric(6, 2) not null default 0,
    enviado_en timestamptz,
    revisado_por uuid references usuarios(id),
    revisado_en timestamptz,
    creado_en timestamptz not null default now(),
    actualizado_en timestamptz not null default now(),
    unique (consultor_id, proyecto_id, periodo)
);

-- ------------------------------------------------------------
-- Detalle de horas por día/actividad - RF-01
-- ------------------------------------------------------------
create table if not exists timesheet_detalles (
    id uuid primary key default gen_random_uuid(),
    timesheet_id uuid not null references timesheets(id) on delete cascade,
    fecha date not null,
    actividad text not null,
    horas numeric(4, 2) not null check (horas > 0 and horas <= 24),
    creado_en timestamptz not null default now()
);

-- ------------------------------------------------------------
-- Historial de aprobaciones / comentarios - RF-05, RF-12
-- ------------------------------------------------------------
create table if not exists timesheet_historial (
    id uuid primary key default gen_random_uuid(),
    timesheet_id uuid not null references timesheets(id) on delete cascade,
    usuario_id uuid not null references usuarios(id),
    tipo_evento tipo_evento_historial not null,
    comentario text,
    creado_en timestamptz not null default now()
);

-- Índices útiles para búsqueda y filtrado (RF-10)
create index if not exists idx_timesheets_consultor on timesheets(consultor_id);
create index if not exists idx_timesheets_proyecto on timesheets(proyecto_id);
create index if not exists idx_timesheets_estado on timesheets(estado);
create index if not exists idx_timesheets_periodo on timesheets(periodo);
create index if not exists idx_historial_timesheet on timesheet_historial(timesheet_id);
