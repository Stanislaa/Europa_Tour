-- SQL-схема ООО «Европа-Тур» для MySQL 8.0
SET NAMES utf8mb4;
SET FOREIGN_KEY_CHECKS = 0;

CREATE TABLE countries (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(120) NOT NULL,
    code CHAR(2) NOT NULL UNIQUE,
    visa_required TINYINT(1) NOT NULL DEFAULT 0
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE hotels (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    country_id BIGINT NOT NULL,
    name VARCHAR(200) NOT NULL,
    city VARCHAR(120) NOT NULL,
    star_rating TINYINT NOT NULL DEFAULT 4,
    CONSTRAINT fk_hotels_country FOREIGN KEY (country_id)
        REFERENCES countries(id) ON DELETE RESTRICT,
    FULLTEXT KEY ft_hotels_name (name) WITH PARSER ngram
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE users (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    email VARCHAR(255) NOT NULL UNIQUE,
    password_hash VARCHAR(255) NOT NULL,
    first_name VARCHAR(80) DEFAULT '',
    last_name VARCHAR(80) DEFAULT '',
    phone VARCHAR(20) DEFAULT '',
    role ENUM('client','manager','admin') NOT NULL DEFAULT 'client',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE tours (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    title VARCHAR(255) NOT NULL,
    country_id BIGINT NOT NULL,
    hotel_id BIGINT NOT NULL,
    nights_min TINYINT NOT NULL DEFAULT 7,
    nights_max TINYINT NOT NULL DEFAULT 14,
    board_type ENUM('RO','BB','HB','FB','AI','UAI') NOT NULL DEFAULT 'AI',
    price_per_night DECIMAL(10,2) NOT NULL,
    description TEXT,
    image_url VARCHAR(500) DEFAULT '',
    is_active TINYINT(1) NOT NULL DEFAULT 1,
    CONSTRAINT fk_tours_country FOREIGN KEY (country_id) REFERENCES countries(id),
    CONSTRAINT fk_tours_hotel FOREIGN KEY (hotel_id) REFERENCES hotels(id),
    INDEX ix_tours_price (price_per_night),
    FULLTEXT KEY ft_tours_title (title, description) WITH PARSER ngram
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE bookings (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    user_id BIGINT NOT NULL,
    tour_id BIGINT NOT NULL,
    check_in DATE NOT NULL,
    nights TINYINT NOT NULL,
    adults TINYINT NOT NULL DEFAULT 1,
    children TINYINT NOT NULL DEFAULT 0,
    total_price DECIMAL(12,2) NOT NULL,
    status ENUM('created','paid','confirmed','cancelled') NOT NULL DEFAULT 'created',
    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_bookings_user FOREIGN KEY (user_id) REFERENCES users(id),
    CONSTRAINT fk_bookings_tour FOREIGN KEY (tour_id) REFERENCES tours(id),
    INDEX ix_bookings_user (user_id),
    INDEX ix_bookings_status (status, check_in)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE favorites (
    user_id BIGINT NOT NULL,
    tour_id BIGINT NOT NULL,
    added_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (user_id, tour_id),
    CONSTRAINT fk_fav_user FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    CONSTRAINT fk_fav_tour FOREIGN KEY (tour_id) REFERENCES tours(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

SET FOREIGN_KEY_CHECKS = 1;
