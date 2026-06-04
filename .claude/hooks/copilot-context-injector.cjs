#!/usr/bin/env node
/**
 * Copilot CLI adapter for Amp person + company context injectors
 * 
 * Copilot CLI sends preToolUse: {"toolName":"view","toolArgs":"{\"path\":\"/some/file\"}"}
 * Claude Code expects:          {"tool_input":{"path":"/some/file"}}
 * 
 * This adapter normalizes the format and calls the original injectors.
 */
const fs = require('fs');
const path = require('path');
const { execSync } = require('child_process');

let rawInput;
try {
  rawInput = fs.readFileSync(0, 'utf-8');
} catch (e) {
  process.exit(0);
}

let input;
try {
  input = JSON.parse(rawInput);
} catch (e) {
  process.exit(0);
}

// Only trigger on file-reading tools. Accept the payload shapes Copilot CLI has used over time.
const toolName = (input.toolName || input.tool_name || input.tool || '').toLowerCase();
if (!['view', 'read', 'read_file'].includes(toolName)) {
  process.exit(0);
}

// Normalize Copilot CLI format → Claude Code format.
let rawArgs = input.toolArgs;
if (rawArgs === undefined || rawArgs === null) rawArgs = input.tool_args;
if (rawArgs === undefined || rawArgs === null) rawArgs = input.args;
if (rawArgs === undefined || rawArgs === null) rawArgs = {};

let toolInput = {};
try {
  if (typeof rawArgs === 'string') {
    toolInput = JSON.parse(rawArgs);
  } else if (Array.isArray(rawArgs)) {
    toolInput = { argv: rawArgs };
  } else if (typeof rawArgs === 'object') {
    toolInput = rawArgs;
  }
} catch (e) {
  process.exit(0);
}

const claudeFormat = JSON.stringify({
  tool_name: toolName,
  tool_input: toolInput
});

// Determine vault root
const VAULT_ROOT = process.env.CLAUDE_PROJECT_DIR || input.cwd || process.cwd();

// Run person context injector
const personScript = path.join(VAULT_ROOT, '.claude', 'hooks', 'person-context-injector.cjs');
if (fs.existsSync(personScript)) {
  try {
    const result = execSync(`node "${personScript}"`, {
      input: claudeFormat,
      env: { ...process.env, CLAUDE_PROJECT_DIR: VAULT_ROOT },
      timeout: 5000,
      encoding: 'utf-8'
    });
    if (result.trim()) process.stdout.write(result);
  } catch (e) {
    process.stderr.write(`[amp-hook] person-context-injector: ${e.message}\n`);
  }
}

// Run company context injector
const companyScript = path.join(VAULT_ROOT, '.claude', 'hooks', 'company-context-injector.cjs');
if (fs.existsSync(companyScript)) {
  try {
    const result = execSync(`node "${companyScript}"`, {
      input: claudeFormat,
      env: { ...process.env, CLAUDE_PROJECT_DIR: VAULT_ROOT },
      timeout: 5000,
      encoding: 'utf-8'
    });
    if (result.trim()) process.stdout.write(result);
  } catch (e) {
    process.stderr.write(`[amp-hook] company-context-injector: ${e.message}\n`);
  }
}
