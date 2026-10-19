--  БАЗА ДАННЫХ ЧАСТНОЙ КЛИНИКИ

CREATE EXTENSION IF NOT EXISTS btree_gist;

CREATE TYPE slot_status AS ENUM ('free', 'booked', 'unavailable');

CREATE TYPE appointment_status AS ENUM ('planned', 'canceled', 'completed', 'no_show');

CREATE TYPE cancel_initiator AS ENUM ('patient', 'administrator');

-- 1. ПАЦИЕНТЫ

CREATE TABLE patients (
    id INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    first_name VARCHAR(100) NOT NULL,
    last_name VARCHAR(100) NOT NULL,
    middle_name VARCHAR(100),
    birth_date DATE,
    phone VARCHAR(20) UNIQUE,
    email VARCHAR(255) UNIQUE,
    guardian_id INT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT chk_patient_contact CHECK (
        phone IS NOT NULL
        OR email IS NOT NULL
        OR guardian_id IS NOT NULL
    ),
    CONSTRAINT chk_patient_phone_format CHECK (phone ~ '^\+[0-9]{10,15}$'),
    CONSTRAINT chk_patient_email_format CHECK (
        email ~ '^[a-z0-9._%+-]+@([a-z0-9-]+\.)+[a-z]{2,}$'
    ),
    CONSTRAINT chk_patient_not_own_guardian CHECK (guardian_id <> id),
    CONSTRAINT fk_patients_guardian FOREIGN KEY (guardian_id) REFERENCES patients (id) ON DELETE RESTRICT ON UPDATE CASCADE
);

CREATE INDEX idx_patients_name ON patients (last_name, first_name);

CREATE INDEX idx_patients_guardian ON patients (guardian_id);

-- 2. СПЕЦИАЛЬНОСТИ

CREATE TABLE specialties (
    id INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    name VARCHAR(100) NOT NULL UNIQUE
);

-- 3. ВРАЧИ

CREATE TABLE doctors (
    id INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    first_name VARCHAR(100) NOT NULL,
    last_name VARCHAR(100) NOT NULL,
    middle_name VARCHAR(100),
    specialty_id INT NOT NULL,
    phone VARCHAR(20) NOT NULL UNIQUE,
    email VARCHAR(255) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    CONSTRAINT chk_doctor_phone_format CHECK (phone ~ '^\+[0-9]{10,15}$'),
    CONSTRAINT chk_doctor_email_format CHECK (
        email ~ '^[a-z0-9._%+-]+@([a-z0-9-]+\.)+[a-z]{2,}$'
    ),
    CONSTRAINT fk_doctors_specialty FOREIGN KEY (specialty_id) REFERENCES specialties (id) ON DELETE RESTRICT ON UPDATE CASCADE
);

CREATE INDEX idx_doctors_specialty ON doctors (specialty_id);

-- 4. УСЛУГИ

CREATE TABLE services (
    id INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    specialty_id INT,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    price NUMERIC(10, 2) CHECK (price > 0),
    CONSTRAINT fk_services_specialty FOREIGN KEY (specialty_id) REFERENCES specialties (id) ON DELETE RESTRICT ON UPDATE CASCADE
);

-- 5. РАСПИСАНИЕ ВРАЧЕЙ

CREATE TABLE schedule (
    id INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    doctor_id INT NOT NULL,
    work_date DATE NOT NULL,
    start_time TIME NOT NULL,
    end_time TIME NOT NULL,
    status slot_status NOT NULL DEFAULT 'free',
    CONSTRAINT fk_schedule_doctor FOREIGN KEY (doctor_id) REFERENCES doctors (id) ON DELETE CASCADE ON UPDATE CASCADE,
    CONSTRAINT chk_schedule_time CHECK (end_time > start_time),
    CONSTRAINT unique_doctor_slot UNIQUE (
        doctor_id,
        work_date,
        start_time
    ),
    CONSTRAINT excl_schedule_no_overlap EXCLUDE USING gist (
        doctor_id
        WITH
            =,
            tsrange (
                work_date + start_time,
                work_date + end_time
            )
        WITH
            &&
    )
);

-- 6. АДМИНИСТРАТОРЫ

CREATE TABLE administrators (
    id INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    first_name VARCHAR(100) NOT NULL,
    last_name VARCHAR(100) NOT NULL,
    phone VARCHAR(20) NOT NULL UNIQUE,
    email VARCHAR(255) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    CONSTRAINT chk_admin_phone_format CHECK (phone ~ '^\+[0-9]{10,15}$'),
    CONSTRAINT chk_admin_email_format CHECK (
        email ~ '^[a-z0-9._%+-]+@([a-z0-9-]+\.)+[a-z]{2,}$'
    )
);

-- 7. ЗАПИСИ НА ПРИЁМ

CREATE TABLE appointments (
    id INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    patient_id INT NOT NULL,
    schedule_id INT NOT NULL,
    status appointment_status NOT NULL DEFAULT 'planned',
    cancel_reason TEXT,
    canceled_at TIMESTAMPTZ,
    canceled_by cancel_initiator,
    conclusion TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT chk_appointment_cancel CHECK (
        (
            status = 'canceled'
            AND cancel_reason IS NOT NULL
            AND btrim(cancel_reason) <> ''
            AND canceled_at IS NOT NULL
            AND canceled_by IS NOT NULL
        )
        OR (
            status <> 'canceled'
            AND cancel_reason IS NULL
            AND canceled_at IS NULL
            AND canceled_by IS NULL
        )
    ),
    CONSTRAINT chk_appointment_conclusion CHECK (
        (
            status = 'completed'
            AND conclusion IS NOT NULL
            AND btrim(conclusion) <> ''
        )
        OR (
            status <> 'completed'
            AND conclusion IS NULL
        )
    ),
    CONSTRAINT fk_appointments_patient FOREIGN KEY (patient_id) REFERENCES patients (id) ON DELETE RESTRICT ON UPDATE CASCADE,
    CONSTRAINT fk_appointments_schedule FOREIGN KEY (schedule_id) REFERENCES schedule (id) ON DELETE RESTRICT ON UPDATE CASCADE,
    CONSTRAINT unique_appointment_id_patient UNIQUE (id, patient_id)
);

CREATE INDEX idx_appointments_patient ON appointments (patient_id);

CREATE INDEX idx_appointments_schedule ON appointments (schedule_id);

CREATE UNIQUE INDEX uq_appointments_active_slot ON appointments (schedule_id)
WHERE
    status <> 'canceled';

-- 8. АНАЛИЗЫ
CREATE TABLE analyses (
    id INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    patient_id INT NOT NULL,
    appointment_id INT,
    name VARCHAR(255) NOT NULL,
    analysis_date DATE NOT NULL,
    result TEXT,
    file_path VARCHAR(500),
    comment TEXT,
    CONSTRAINT fk_analyses_patient FOREIGN KEY (patient_id) REFERENCES patients (id) ON DELETE RESTRICT ON UPDATE CASCADE,
    CONSTRAINT fk_analyses_appointment FOREIGN KEY (appointment_id, patient_id) REFERENCES appointments (id, patient_id) ON DELETE SET NULL (appointment_id) ON UPDATE CASCADE
);

CREATE INDEX idx_analyses_patient ON analyses (patient_id);

-- 9. БОЛЬНИЧНЫЕ
CREATE TABLE sick_leaves (
    id INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    patient_id INT NOT NULL,
    doctor_id INT,
    start_date DATE NOT NULL,
    end_date DATE NOT NULL,
    diagnosis VARCHAR(255),
    CONSTRAINT chk_sick_leaves_dates CHECK (end_date >= start_date),
    CONSTRAINT fk_sick_leaves_patient FOREIGN KEY (patient_id) REFERENCES patients (id) ON DELETE RESTRICT ON UPDATE CASCADE,
    CONSTRAINT fk_sick_leaves_doctor FOREIGN KEY (doctor_id) REFERENCES doctors (id) ON DELETE SET NULL ON UPDATE CASCADE
);

CREATE INDEX idx_sick_leaves_patient ON sick_leaves (patient_id);

-- 10. СПРАВКИ
CREATE TABLE certificates (
    id INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    patient_id INT NOT NULL,
    doctor_id INT,
    type VARCHAR(255) NOT NULL,
    issue_date DATE NOT NULL,
    description TEXT,
    CONSTRAINT fk_certificates_patient FOREIGN KEY (patient_id) REFERENCES patients (id) ON DELETE RESTRICT ON UPDATE CASCADE,
    CONSTRAINT fk_certificates_doctor FOREIGN KEY (doctor_id) REFERENCES doctors (id) ON DELETE SET NULL ON UPDATE CASCADE
);

CREATE INDEX idx_certificates_patient ON certificates (patient_id);

-- 11. РЕЦЕПТЫ
CREATE TABLE prescriptions (
    id INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    appointment_id INT NOT NULL,
    prescription_date DATE NOT NULL DEFAULT CURRENT_DATE,
    medicine VARCHAR(255) NOT NULL,
    dosage VARCHAR(100),
    instructions TEXT,
    CONSTRAINT fk_prescriptions_appointment FOREIGN KEY (appointment_id) REFERENCES appointments (id) ON DELETE RESTRICT ON UPDATE CASCADE
);

CREATE INDEX idx_prescriptions_appointment ON prescriptions (appointment_id);

-- 12. КОДЫ ВХОДА
CREATE TABLE login_codes (
    id INT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    contact VARCHAR(255) NOT NULL,
    code_hash VARCHAR(255) NOT NULL,
    expires_at TIMESTAMPTZ NOT NULL,
    attempts INT NOT NULL DEFAULT 0,
    used_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_login_codes_contact ON login_codes (contact, created_at DESC);