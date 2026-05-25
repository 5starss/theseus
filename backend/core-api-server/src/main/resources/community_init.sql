CREATE TABLE IF NOT EXISTS community_posts (
    community_post_id BIGINT NOT NULL AUTO_INCREMENT,
    user_id BIGINT NOT NULL,
    ticker VARCHAR(20) NOT NULL,
    title VARCHAR(200) NOT NULL,
    content TEXT NOT NULL,
    view_count BIGINT NOT NULL DEFAULT 0,
    comment_count BIGINT NOT NULL DEFAULT 0,
    created_at DATETIME NULL,
    updated_at DATETIME NULL,
    PRIMARY KEY (community_post_id),
    CONSTRAINT fk_community_posts_stock
        FOREIGN KEY (ticker) REFERENCES stocks (ticker),
    INDEX idx_community_posts_ticker_created_at (ticker, created_at DESC, community_post_id DESC),
    INDEX idx_community_posts_user_id (user_id)
);

CREATE TABLE IF NOT EXISTS community_comments (
    community_comment_id BIGINT NOT NULL AUTO_INCREMENT,
    community_post_id BIGINT NOT NULL,
    user_id BIGINT NOT NULL,
    content TEXT NOT NULL,
    created_at DATETIME NULL,
    updated_at DATETIME NULL,
    PRIMARY KEY (community_comment_id),
    CONSTRAINT fk_community_comments_post
        FOREIGN KEY (community_post_id) REFERENCES community_posts (community_post_id)
        ON DELETE CASCADE,
    INDEX idx_community_comments_post_created_at (community_post_id, created_at ASC, community_comment_id ASC),
    INDEX idx_community_comments_user_id (user_id)
);

SET @schema_name = DATABASE();

SET @ddl = (
    SELECT IF(
        EXISTS(
            SELECT 1
            FROM information_schema.table_constraints
            WHERE table_schema = @schema_name
              AND table_name = 'community_posts'
              AND constraint_name = 'fk_community_posts_stock'
              AND constraint_type = 'FOREIGN KEY'
        ),
        'SELECT 1',
        'ALTER TABLE community_posts ADD CONSTRAINT fk_community_posts_stock FOREIGN KEY (ticker) REFERENCES stocks (ticker)'
    )
);
PREPARE stmt FROM @ddl;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

CREATE TABLE IF NOT EXISTS community_post_likes (
    community_post_like_id BIGINT NOT NULL AUTO_INCREMENT,
    community_post_id BIGINT NOT NULL,
    user_id BIGINT NOT NULL,
    PRIMARY KEY (community_post_like_id),
    CONSTRAINT fk_community_post_likes_post
        FOREIGN KEY (community_post_id) REFERENCES community_posts (community_post_id)
        ON DELETE CASCADE,
    CONSTRAINT uk_community_post_likes_user_post
        UNIQUE (user_id, community_post_id),
    INDEX idx_community_post_likes_post_id (community_post_id),
    INDEX idx_community_post_likes_user_id (user_id)
);

CREATE TABLE IF NOT EXISTS community_comment_likes (
    community_comment_like_id BIGINT NOT NULL AUTO_INCREMENT,
    community_comment_id BIGINT NOT NULL,
    user_id BIGINT NOT NULL,
    PRIMARY KEY (community_comment_like_id),
    CONSTRAINT fk_community_comment_likes_comment
        FOREIGN KEY (community_comment_id) REFERENCES community_comments (community_comment_id)
        ON DELETE CASCADE,
    CONSTRAINT uk_community_comment_likes_user_comment
        UNIQUE (user_id, community_comment_id),
    INDEX idx_community_comment_likes_comment_id (community_comment_id),
    INDEX idx_community_comment_likes_user_id (user_id)
);

SET @ddl = (
    SELECT IF(
        EXISTS(
            SELECT 1
            FROM information_schema.table_constraints
            WHERE table_schema = @schema_name
              AND table_name = 'community_post_likes'
              AND constraint_name = 'fk_community_post_likes_post'
              AND constraint_type = 'FOREIGN KEY'
        ),
        'SELECT 1',
        'ALTER TABLE community_post_likes ADD CONSTRAINT fk_community_post_likes_post FOREIGN KEY (community_post_id) REFERENCES community_posts (community_post_id) ON DELETE CASCADE'
    )
);
PREPARE stmt FROM @ddl;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @ddl = (
    SELECT IF(
        EXISTS(
            SELECT 1
            FROM information_schema.table_constraints
            WHERE table_schema = @schema_name
              AND table_name = 'community_post_likes'
              AND constraint_name = 'uk_community_post_likes_user_post'
              AND constraint_type = 'UNIQUE'
        ),
        'SELECT 1',
        'ALTER TABLE community_post_likes ADD CONSTRAINT uk_community_post_likes_user_post UNIQUE (user_id, community_post_id)'
    )
);
PREPARE stmt FROM @ddl;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @ddl = (
    SELECT IF(
        EXISTS(
            SELECT 1
            FROM information_schema.statistics
            WHERE table_schema = @schema_name
              AND table_name = 'community_post_likes'
              AND index_name = 'idx_community_post_likes_post_id'
        ),
        'SELECT 1',
        'CREATE INDEX idx_community_post_likes_post_id ON community_post_likes (community_post_id)'
    )
);
PREPARE stmt FROM @ddl;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @ddl = (
    SELECT IF(
        EXISTS(
            SELECT 1
            FROM information_schema.statistics
            WHERE table_schema = @schema_name
              AND table_name = 'community_post_likes'
              AND index_name = 'idx_community_post_likes_user_id'
        ),
        'SELECT 1',
        'CREATE INDEX idx_community_post_likes_user_id ON community_post_likes (user_id)'
    )
);
PREPARE stmt FROM @ddl;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @ddl = (
    SELECT IF(
        EXISTS(
            SELECT 1
            FROM information_schema.table_constraints
            WHERE table_schema = @schema_name
              AND table_name = 'community_comment_likes'
              AND constraint_name = 'fk_community_comment_likes_comment'
              AND constraint_type = 'FOREIGN KEY'
        ),
        'SELECT 1',
        'ALTER TABLE community_comment_likes ADD CONSTRAINT fk_community_comment_likes_comment FOREIGN KEY (community_comment_id) REFERENCES community_comments (community_comment_id) ON DELETE CASCADE'
    )
);
PREPARE stmt FROM @ddl;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @ddl = (
    SELECT IF(
        EXISTS(
            SELECT 1
            FROM information_schema.table_constraints
            WHERE table_schema = @schema_name
              AND table_name = 'community_comment_likes'
              AND constraint_name = 'uk_community_comment_likes_user_comment'
              AND constraint_type = 'UNIQUE'
        ),
        'SELECT 1',
        'ALTER TABLE community_comment_likes ADD CONSTRAINT uk_community_comment_likes_user_comment UNIQUE (user_id, community_comment_id)'
    )
);
PREPARE stmt FROM @ddl;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @ddl = (
    SELECT IF(
        EXISTS(
            SELECT 1
            FROM information_schema.statistics
            WHERE table_schema = @schema_name
              AND table_name = 'community_comment_likes'
              AND index_name = 'idx_community_comment_likes_comment_id'
        ),
        'SELECT 1',
        'CREATE INDEX idx_community_comment_likes_comment_id ON community_comment_likes (community_comment_id)'
    )
);
PREPARE stmt FROM @ddl;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @ddl = (
    SELECT IF(
        EXISTS(
            SELECT 1
            FROM information_schema.statistics
            WHERE table_schema = @schema_name
              AND table_name = 'community_comment_likes'
              AND index_name = 'idx_community_comment_likes_user_id'
        ),
        'SELECT 1',
        'CREATE INDEX idx_community_comment_likes_user_id ON community_comment_likes (user_id)'
    )
);
PREPARE stmt FROM @ddl;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @ddl = (
    SELECT IF(
        EXISTS(
            SELECT 1
            FROM information_schema.statistics
            WHERE table_schema = @schema_name
              AND table_name = 'community_posts'
              AND index_name = 'idx_community_posts_ticker_created_at'
        ),
        'SELECT 1',
        'CREATE INDEX idx_community_posts_ticker_created_at ON community_posts (ticker, created_at DESC, community_post_id DESC)'
    )
);
PREPARE stmt FROM @ddl;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @ddl = (
    SELECT IF(
        EXISTS(
            SELECT 1
            FROM information_schema.statistics
            WHERE table_schema = @schema_name
              AND table_name = 'community_posts'
              AND index_name = 'idx_community_posts_user_id'
        ),
        'SELECT 1',
        'CREATE INDEX idx_community_posts_user_id ON community_posts (user_id)'
    )
);
PREPARE stmt FROM @ddl;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @ddl = (
    SELECT IF(
        EXISTS(
            SELECT 1
            FROM information_schema.table_constraints
            WHERE table_schema = @schema_name
              AND table_name = 'community_comments'
              AND constraint_name = 'fk_community_comments_post'
              AND constraint_type = 'FOREIGN KEY'
        ),
        'SELECT 1',
        'ALTER TABLE community_comments ADD CONSTRAINT fk_community_comments_post FOREIGN KEY (community_post_id) REFERENCES community_posts (community_post_id) ON DELETE CASCADE'
    )
);
PREPARE stmt FROM @ddl;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @ddl = (
    SELECT IF(
        EXISTS(
            SELECT 1
            FROM information_schema.statistics
            WHERE table_schema = @schema_name
              AND table_name = 'community_comments'
              AND index_name = 'idx_community_comments_post_created_at'
        ),
        'SELECT 1',
        'CREATE INDEX idx_community_comments_post_created_at ON community_comments (community_post_id, created_at ASC, community_comment_id ASC)'
    )
);
PREPARE stmt FROM @ddl;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @ddl = (
    SELECT IF(
        EXISTS(
            SELECT 1
            FROM information_schema.statistics
            WHERE table_schema = @schema_name
              AND table_name = 'community_comments'
              AND index_name = 'idx_community_comments_user_id'
        ),
        'SELECT 1',
        'CREATE INDEX idx_community_comments_user_id ON community_comments (user_id)'
    )
);
PREPARE stmt FROM @ddl;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;
