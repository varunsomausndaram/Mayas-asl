'use strict';

const express = require('express');
const gateway = require('../gateway');

const router = express.Router();

router.get('/', async (_req, res) => {
  const result = await gateway.healthCheck();
  res.status(result.ok ? 200 : 503).json(result);
});

module.exports = router;
