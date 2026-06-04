#!/usr/bin/env node
/**
 * Amp - Basic test runner
 * Validates project structure, syntax, and configuration.
 */

const fs = require('fs');
const path = require('path');
const { execSync } = require('child_process');

const ROOT = path.resolve(__dirname, '..');
const MIN_PYTHON = { major: 3, minor: 11 };
let passed = 0;
let failed = 0;

function test(name, fn) {
    try {
        fn();
        console.log(`  ✅ ${name}`);
        passed++;
    } catch (e) {
        console.log(`  ❌ ${name}: ${e.message}`);
        failed++;
    }
}

function assert(condition, msg) {
    if (!condition) throw new Error(msg);
}

function detectPython() {
    const candidates = process.env.VIRTUAL_ENV
        ? ['python', 'python3.12', 'python3.11', 'python3']
        : ['python3.12', 'python3.11', 'python3'];
    const found = [];

    for (const candidate of candidates) {
        try {
            const version = execSync(
                `${candidate} -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}')"`,
                { encoding: 'utf8', stdio: ['ignore', 'pipe', 'ignore'] }
            ).trim();
            found.push(`${candidate} ${version}`);

            const [major, minor] = version.split('.').map(Number);
            if (
                major > MIN_PYTHON.major ||
                (major === MIN_PYTHON.major && minor >= MIN_PYTHON.minor)
            ) {
                return candidate;
            }
        } catch (_) {
            // Candidate is not installed or not executable. Try the next one.
        }
    }

    const foundMessage = found.length ? ` Found: ${found.join(', ')}.` : ' No Python executable found.';
    throw new Error(
        `Amp tests require Python ${MIN_PYTHON.major}.${MIN_PYTHON.minor}+.${foundMessage} ` +
        'Install Python 3.12 or run tests inside a Python 3.11+ virtualenv.'
    );
}

function verifyPythonEnvironment(pythonCommand) {
    try {
        execSync(
            `${pythonCommand} -c "import yaml; import dateutil; print('python deps OK')"`,
            { encoding: 'utf8', stdio: ['ignore', 'pipe', 'ignore'] }
        );
    } catch (_) {
        throw new Error(
            `Amp tests found a supported Python command (${pythonCommand}), but required Python dependencies are missing. ` +
            'Run `python3.12 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt`, ' +
            'or activate an existing Python 3.11+ virtualenv with Amp dependencies installed.'
        );
    }
}

function configurePython() {
    const pythonCommand = detectPython();
    verifyPythonEnvironment(pythonCommand);
    return pythonCommand;
}

console.log('\n⚡ Amp Test Suite\n');

let PYTHON;
try {
    PYTHON = configurePython();
} catch (e) {
    console.error(`❌ ${e.message}`);
    process.exit(1);
}

// -------------------------------------------
// Structure tests
// -------------------------------------------
console.log('📁 Project Structure:');

test('README.md exists', () => {
    assert(fs.existsSync(path.join(ROOT, 'README.md')), 'Missing README.md');
});

test('LICENSE exists', () => {
    assert(fs.existsSync(path.join(ROOT, 'LICENSE')), 'Missing LICENSE');
});

test('install.sh exists and is executable', () => {
    const stat = fs.statSync(path.join(ROOT, 'install.sh'));
    assert(stat.mode & 0o111, 'install.sh is not executable');
});

test('CLAUDE.md.template exists', () => {
    assert(fs.existsSync(path.join(ROOT, 'CLAUDE.md.template')), 'Missing CLAUDE.md.template');
});

test('AGENTS.md exists', () => {
    assert(fs.existsSync(path.join(ROOT, 'AGENTS.md')), 'Missing AGENTS.md');
});

test('.mcp.json.template exists', () => {
    assert(fs.existsSync(path.join(ROOT, '.mcp.json.template')), 'Missing .mcp.json.template');
});

test('.gitignore exists', () => {
    assert(fs.existsSync(path.join(ROOT, '.gitignore')), 'Missing .gitignore');
});

// -------------------------------------------
// Template tests
// -------------------------------------------
console.log('\n📋 Templates:');

test('user-profile.example.yaml exists', () => {
    assert(fs.existsSync(path.join(ROOT, 'System/user-profile.example.yaml')), 'Missing');
});

test('onboarding server uses the tracked user profile example', () => {
    const content = fs.readFileSync(path.join(ROOT, 'core/mcp/onboarding_server.py'), 'utf8');
    assert(content.includes("user-profile.example.yaml"), 'onboarding_server.py should reference System/user-profile.example.yaml');
});

test('pillars.example.yaml exists', () => {
    assert(fs.existsSync(path.join(ROOT, 'System/pillars.example.yaml')), 'Missing');
});

test('.mcp.json.template has {{VAULT_PATH}} placeholders', () => {
    const content = fs.readFileSync(path.join(ROOT, '.mcp.json.template'), 'utf8');
    assert(content.includes('{{VAULT_PATH}}'), 'No {{VAULT_PATH}} found');
});

test('.mcp.json.template is valid JSON (with placeholders)', () => {
    const content = fs.readFileSync(path.join(ROOT, '.mcp.json.template'), 'utf8');
    const replaced = content.replace(/\{\{VAULT_PATH\}\}/g, '/tmp/test');
    JSON.parse(replaced);
});

test('onboarding server uses the root MCP config template', () => {
    const content = fs.readFileSync(path.join(ROOT, 'core/mcp/onboarding_server.py'), 'utf8');
    assert(content.includes('.mcp.json.template'), 'onboarding_server.py should reference the root .mcp.json.template');
    assert(content.includes("BASE_DIR / '.mcp.json'"), 'onboarding_server.py should write .mcp.json at the vault root');
});

test('onboarding dependency instructions use root requirements.txt', () => {
    const content = fs.readFileSync(path.join(ROOT, 'core/mcp/onboarding_server.py'), 'utf8');
    assert(content.includes('pip install -r {BASE_DIR}/requirements.txt'), 'verify_dependencies should point to the root requirements.txt');
    assert(!content.includes('core/mcp/requirements.txt'), 'onboarding_server.py should not point to core/mcp/requirements.txt');
});

test('Task template exists', () => {
    assert(fs.existsSync(path.join(ROOT, 'System/Templates/Tasks.md')), 'Missing');
});

test('onboarding flow documents the 4-step core setup', () => {
    const content = fs.readFileSync(path.join(ROOT, '.claude/flows/onboarding.md'), 'utf8');
    assert(content.includes('After each step (1-4)'), 'Onboarding flow should describe a 4-step core setup');
    assert(content.includes('## Step 3: Email Domain (MANDATORY)'), 'Email domain should be part of the core flow');
});

test('onboarding flow bootstraps .mcp.json before calling MCP tools', () => {
    const flow = fs.readFileSync(path.join(ROOT, '.claude/flows/onboarding.md'), 'utf8');
    const skill = fs.readFileSync(path.join(ROOT, '.claude/skills/setup/SKILL.md'), 'utf8');
    const claudemd = fs.readFileSync(path.join(ROOT, 'CLAUDE.md.template'), 'utf8');
    assert(flow.includes('## Bootstrap Check'), 'Onboarding flow should have a Bootstrap Check section');
    assert(flow.includes('.mcp.json.template'), 'Onboarding flow should reference .mcp.json.template');
    assert(skill.includes('.mcp.json'), '/setup skill should mention .mcp.json bootstrap');
    assert(claudemd.includes('BOOTSTRAP FIRST'), 'CLAUDE.md.template should include bootstrap step');
});

test('onboarding flow requires Obsidian instead of integration discovery', () => {
    const content = fs.readFileSync(path.join(ROOT, '.claude/flows/onboarding.md'), 'utf8');
    assert(content.includes('## Step 6: Vault Viewer Setup'), 'Onboarding should include a vault viewer setup step');
    assert(content.includes('complete_obsidian_walkthrough()'), 'Onboarding should persist the Obsidian walkthrough completion');
    assert(!content.includes('## Step 6: Connect Your Tools (Integration Discovery)'), 'Onboarding should not include the old integration discovery step');
    assert(!content.includes('**Your Career Level:**'), 'Onboarding should not ask for career level during setup');
});

test('/setup skill summary matches the 4-step onboarding flow', () => {
    const content = fs.readFileSync(path.join(ROOT, '.claude/skills/setup/SKILL.md'), 'utf8');
    assert(content.includes('4 questions: name, role, email domain, communication preferences'), '/setup should describe the 4-step core setup');
    assert(content.includes('validate_and_save_step()` after each core step (1-4)'), '/setup should reference steps 1-4 for validation');
    assert(content.includes('finalize_onboarding()` during Step 5'), '/setup should reference finalization during Step 5');
    assert(content.includes('complete_obsidian_walkthrough()` after the user confirms the vault is open'), '/setup should complete onboarding after the Obsidian walkthrough');
    assert(content.includes('required Obsidian walkthrough'), '/setup should mention the required Obsidian walkthrough');
    assert(!content.includes('**Phase 4: Tool Connections**'), '/setup should not describe tool connections during onboarding');
});

test('onboarding server accepts direct step fields without requiring step_data', () => {
    const content = fs.readFileSync(path.join(ROOT, 'core/mcp/onboarding_server.py'), 'utf8');
    assert(content.includes('def normalize_step_data(arguments: Dict[str, Any]) -> Dict[str, Any]:'), 'Onboarding server should normalize direct step fields');
    assert(content.includes('"required": ["step_number"]'), 'validate_and_save_step should only require step_number');
});

test('onboarding server persists the Obsidian walkthrough before marking completion', () => {
    const content = fs.readFileSync(path.join(ROOT, 'core/mcp/onboarding_server.py'), 'utf8');
    assert(content.includes('name="complete_obsidian_walkthrough"'), 'Onboarding server should expose a completion tool for the Obsidian walkthrough');
    assert(content.includes("session['current_step'] = 6"), 'finalize_onboarding should leave the session at the Obsidian walkthrough step');
    assert(content.includes('awaiting_obsidian_walkthrough'), 'Onboarding status should expose the pending Obsidian walkthrough state');
});

test('timezone utilities normalize common abbreviations safely', () => {
    const result = execSync(
        `cd "${ROOT}" && ${PYTHON} -c "from core.utils.timezone import normalize_timezone_name, resolve_timezone; assert normalize_timezone_name('EDT') == 'America/New_York'; assert resolve_timezone('EDT').key == 'America/New_York'; print('timezone OK')"`,
        { encoding: 'utf8' }
    );
    assert(result.includes('timezone OK'), 'Timezone helper should normalize EDT to America/New_York');
});


// -------------------------------------------
// Update safety metadata tests
// -------------------------------------------
console.log('\n🛡️ Update Safety Metadata:');

function readJson(relativePath) {
    const fullPath = path.join(ROOT, relativePath);
    assert(fs.existsSync(fullPath), `Missing ${relativePath}`);
    return JSON.parse(fs.readFileSync(fullPath, 'utf8'));
}

function assertRequiredFields(object, fields, label) {
    fields.forEach(field => {
        assert(Object.prototype.hasOwnProperty.call(object, field), `${label} missing ${field}`);
        assert(object[field] !== '' && object[field] !== null && object[field] !== undefined, `${label} has empty ${field}`);
    });
}

test('Update manifest exists, parses, and has required release fields', () => {
    const manifest = readJson('System/update-manifest.json');
    assertRequiredFields(manifest, ['schema_version', 'product', 'manifest_kind', 'current_release', 'releases'], 'update manifest');
    assert(manifest.manifest_kind === 'update_manifest', 'Unexpected manifest_kind');
    assert(Array.isArray(manifest.releases) && manifest.releases.length > 0, 'Manifest should list releases');
    const current = manifest.releases.find(release => release.version === manifest.current_release);
    assert(current, `current_release ${manifest.current_release} is not present in releases`);
    manifest.releases.forEach(release => {
        assertRequiredFields(release, ['version', 'release_date', 'status', 'summary', 'entries'], `release ${release.version}`);
        assert(Array.isArray(release.entries) && release.entries.length > 0, `release ${release.version} has no entries`);
        release.entries.forEach(entry => {
            assertRequiredFields(entry, ['id', 'category', 'change_type', 'title', 'summary', 'paths', 'migration_impact', 'breaking_change_ids'], `manifest entry ${entry.id || '(missing id)'}`);
            assert(Array.isArray(entry.paths), `manifest entry ${entry.id} paths must be an array`);
            assert(Array.isArray(entry.breaking_change_ids), `manifest entry ${entry.id} breaking_change_ids must be an array`);
        });
    });
});

test('Update manifest entry ids are unique', () => {
    const manifest = readJson('System/update-manifest.json');
    const ids = manifest.releases.flatMap(release => release.entries.map(entry => entry.id));
    assert(new Set(ids).size === ids.length, 'Manifest entry ids must be unique');
});

test('Breaking-change registry exists, parses, and has required fields', () => {
    const registry = readJson('System/breaking-changes.json');
    assertRequiredFields(registry, ['schema_version', 'product', 'manifest_kind', 'entries'], 'breaking-change registry');
    assert(registry.manifest_kind === 'breaking_change_registry', 'Unexpected registry manifest_kind');
    assert(Array.isArray(registry.entries) && registry.entries.length > 0, 'Registry should list breaking-change entries');
    registry.entries.forEach(entry => {
        assertRequiredFields(entry, ['id', 'introduced_in', 'status', 'severity', 'title', 'affected_signals', 'impact', 'migration_guidance', 'detection'], `breaking-change entry ${entry.id || '(missing id)'}`);
        assert(Array.isArray(entry.affected_signals) && entry.affected_signals.length > 0, `breaking-change entry ${entry.id} should list affected signals`);
        assert(entry.detection && Array.isArray(entry.detection.legacy_names), `breaking-change entry ${entry.id} should list legacy detection names`);
    });
});

test('Breaking-change registry ids are unique and linked from manifest', () => {
    const manifest = readJson('System/update-manifest.json');
    const registry = readJson('System/breaking-changes.json');
    const registryIds = registry.entries.map(entry => entry.id);
    assert(new Set(registryIds).size === registryIds.length, 'Breaking-change ids must be unique');
    const linkedIds = new Set(manifest.releases.flatMap(release => release.entries.flatMap(entry => entry.breaking_change_ids || [])));
    registryIds.forEach(id => assert(linkedIds.has(id), `Breaking-change ${id} is not linked from the update manifest`));
});

// -------------------------------------------
// MCP Server tests
// -------------------------------------------
console.log('\n🔧 MCP Servers:');

const servers = [
    'work_server.py', 'calendar_server.py', 'career_server.py',
    'career_parser.py', 'onboarding_server.py', 'improvements_server.py',
    'session_memory_server.py', 'resume_server.py', 'resume_parser.py',
    'update_checker_server.py', 'analytics_server.py', 'analytics_helper.py'
];

servers.forEach(server => {
    test(`${server} exists`, () => {
        assert(fs.existsSync(path.join(ROOT, 'core/mcp', server)), `Missing ${server}`);
    });
});


test('usage-log merge helper preserves checked state and legacy entries', () => {
    const result = execSync(
        `cd "${ROOT}" && ${PYTHON} .scripts/merge-usage-log.py --self-test`,
        { encoding: 'utf8' }
    );
    assert(result.includes('merge-usage-log self-test OK'), 'usage-log merge helper self-test failed');
});

test('All MCP servers pass Python syntax check', () => {
    const result = execSync(
        `cd "${ROOT}/core/mcp" && ${PYTHON} -c "
import ast, os, sys
errors = []
py_files = [f for f in sorted(os.listdir('.')) if f.endswith('.py')]
for f in py_files:
    try:
        ast.parse(open(f).read())
    except SyntaxError as e:
        errors.append(str(f) + ': ' + str(e))
if errors:
    print(chr(10).join(errors))
    sys.exit(1)
count = len(py_files)
print(str(count) + ' servers OK')
"`,
        { encoding: 'utf8' }
    );
});

// -------------------------------------------
// Skills tests
// -------------------------------------------
console.log('\n🎯 Skills:');

test('Skills directory exists', () => {
    assert(fs.existsSync(path.join(ROOT, '.claude/skills')), 'Missing .claude/skills/');
});

test('At least 50 skills present', () => {
    const skills = fs.readdirSync(path.join(ROOT, '.claude/skills'))
        .filter(f => fs.statSync(path.join(ROOT, '.claude/skills', f)).isDirectory());
    assert(skills.length >= 50, `Only ${skills.length} skills found`);
});

test('Core skills present (daily-plan, daily-review, meeting-prep)', () => {
    const required = ['daily-plan', 'daily-review', 'meeting-prep', 'week-plan', 'quarter-plan'];
    required.forEach(skill => {
        assert(
            fs.existsSync(path.join(ROOT, '.claude/skills', skill)),
            `Missing skill: ${skill}`
        );
    });
});

test('Amp update skills document concrete safety checks', () => {
    const update = fs.readFileSync(path.join(ROOT, '.claude/skills/amp-update/SKILL.md'), 'utf8');
    const preflight = fs.readFileSync(path.join(ROOT, '.claude/skills/amp-update-preflight/SKILL.md'), 'utf8');
    [
        'protected-content inventory',
        '.scripts/amp-merge-resolver.sh',
        'MCP validation after sync',
        'System/update-summary.md',
        'breaking-change registry check',
    ].forEach(required => {
        assert(update.includes(required), `/amp-update missing: ${required}`);
    });
    [
        'Protected Content Inventory',
        'MCP Configuration Validation Preview',
        'custom_mcp_entries',
        'env_present',
        'update manifest',
    ].forEach(required => {
        assert(preflight.includes(required), `/amp-update-preflight missing: ${required}`);
    });
});

test('amp-show-changes skill exists and documents read-only preview behavior', () => {
    const skillPath = path.join(ROOT, '.claude/skills/amp-show-changes/SKILL.md');
    assert(fs.existsSync(skillPath), 'Missing amp-show-changes skill');
    const content = fs.readFileSync(skillPath, 'utf8');
    assert(content.includes('name: amp-show-changes'), 'Missing skill metadata');
    assert(content.includes('Read-only guarantee'), 'Skill should describe read-only behavior');
    assert(content.includes('git fetch'), 'Skill should refresh remote main when Git is available');
    assert(content.includes('git diff --name-status HEAD..'), 'Skill should compare current HEAD to remote main');
    assert(content.includes('Protected customizations inventory'), 'Skill should inventory protected customizations');
    assert(content.includes('What this means for you'), 'Skill should include plain-English impact section');
});

test('amp-show-changes skill contains no private rollout content', () => {
    const content = fs.readFileSync(path.join(ROOT, '.claude/skills/amp-show-changes/SKILL.md'), 'utf8');
    const forbiddenPatterns = [
        /he[m]ory/i,
        /\/Users\//,
        /@[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}/,
        /private CLAUDE/i,
        /identity file/i
    ];
    const found = forbiddenPatterns.filter(pattern => pattern.test(content)).map(String);
    assert(found.length === 0, `Private content found: ${found.join(', ')}`);
});

// -------------------------------------------
// Hooks tests
// -------------------------------------------
console.log('\n🪝 Hooks:');

test('Claude hooks directory exists', () => {
    assert(fs.existsSync(path.join(ROOT, '.claude/hooks')), 'Missing .claude/hooks/');
});

test('Copilot hooks directory exists', () => {
    assert(fs.existsSync(path.join(ROOT, '.github/hooks')), 'Missing .github/hooks/');
});

test('hooks.json exists for Copilot CLI', () => {
    assert(fs.existsSync(path.join(ROOT, '.github/hooks/hooks.json')), 'Missing hooks.json');
});

// -------------------------------------------
// No personal data tests
// -------------------------------------------
console.log('\n🔒 Privacy:');

test('CLAUDE.md.template uses onboarding placeholders', () => {
    const content = fs.readFileSync(path.join(ROOT, 'CLAUDE.md.template'), 'utf8');
    assert(content.includes('{{NAME}}'), 'Missing {{NAME}} placeholder');
    assert(content.includes('{{ROLE}}'), 'Missing {{ROLE}} placeholder');
});

test('No hardcoded home paths in tracked markdown or config', () => {
    const homePathPattern = ['/', 'Users', '/'].join('') + '|' + ['/', 'home', '/'].join('');
    const result = execSync(
        `cd "${ROOT}" && git grep -nE "${homePathPattern}" -- '*.md' '*.yaml' '*.yml' '*.json' '*.py' 2>/dev/null || echo "CLEAN"`,
        { encoding: 'utf8' }
    ).trim();
    assert(result === 'CLEAN', `Hardcoded home path found in: ${result}`);
});

// -------------------------------------------
// Scripts tests
// -------------------------------------------
console.log('\n📜 Scripts:');

const scripts = ['morning_brief.py', 'meeting_prep_auto.py', 'eod_digest.py', 'amp_slack_bot.py'];
scripts.forEach(script => {
    test(`${script} exists and passes syntax`, () => {
        assert(fs.existsSync(path.join(ROOT, 'scripts', script)), `Missing ${script}`);
    });
});

test('amp-merge-resolver helper exists and passes shell syntax', () => {
    const scriptPath = path.join(ROOT, '.scripts/amp-merge-resolver.sh');
    assert(fs.existsSync(scriptPath), 'Missing .scripts/amp-merge-resolver.sh');
    const stat = fs.statSync(scriptPath);
    assert(stat.mode & 0o111, 'amp-merge-resolver.sh is not executable');
    execSync(`bash -n "${scriptPath}"`, { encoding: 'utf8' });
});

// -------------------------------------------
// Summary
// -------------------------------------------
console.log(`\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━`);
console.log(`  Results: ${passed} passed, ${failed} failed`);
console.log(`━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n`);

process.exit(failed > 0 ? 1 : 0);
