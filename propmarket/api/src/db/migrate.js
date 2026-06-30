'use strict';
/**
 * Minimal migration runner.
 * Reads SQL files from /migrations in numeric order, tracks applied migrations
 * in pm_schema_migrations table.
 */
const fs   = require('fs');
const path = require('path');
const pool = require('./pool');

const MIGRATIONS_DIR = process.env.MIGRATIONS_DIR || path.join(__dirname, '../../../migrations');

async function run() {
  const client = await pool.connect();
  try {
    await client.query(`
      CREATE TABLE IF NOT EXISTS pm_schema_migrations (
        filename  VARCHAR(255) PRIMARY KEY,
        applied_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
      )
    `);

    const { rows: applied } = await client.query(
      'SELECT filename FROM pm_schema_migrations ORDER BY filename'
    );
    const appliedSet = new Set(applied.map((r) => r.filename));

    const files = fs
      .readdirSync(MIGRATIONS_DIR)
      .filter((f) => f.endsWith('.sql'))
      .sort();

    for (const file of files) {
      if (appliedSet.has(file)) continue;
      console.log(`[migrate] Applying ${file}…`);
      const sql = fs.readFileSync(path.join(MIGRATIONS_DIR, file), 'utf8');
      await client.query('BEGIN');
      try {
        await client.query(sql);
        await client.query(
          'INSERT INTO pm_schema_migrations (filename) VALUES ($1)',
          [file]
        );
        await client.query('COMMIT');
        console.log(`[migrate] ✓ ${file}`);
      } catch (err) {
        await client.query('ROLLBACK');
        throw new Error(`Migration ${file} failed: ${err.message}`);
      }
    }

    console.log('[migrate] All migrations applied.');
  } finally {
    client.release();
  }
}

module.exports = { run };
