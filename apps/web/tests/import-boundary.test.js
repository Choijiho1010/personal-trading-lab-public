import { ESLint } from 'eslint';
import { describe, expect, it } from 'vitest';

const eslint = new ESLint({ cwd: process.cwd() });

describe('React import boundaries', () => {
  it('allows the app composition layer to import a feature', async () => {
    const [result] = await eslint.lintText(
      "import { FillQuestionScreen } from '../features/fill-question/fill-question-screen.jsx';",
      { filePath: 'src/app/boundary-fixture.jsx' },
    );

    expect(result.errorCount).toBe(0);
  });

  it('rejects a feature importing the app composition layer', async () => {
    const [result] = await eslint.lintText(
      "import { App } from '../../app/app.jsx';",
      { filePath: 'src/features/fill-question/boundary-fixture.jsx' },
    );

    expect(result.messages).toEqual(expect.arrayContaining([
      expect.objectContaining({ ruleId: 'import/no-restricted-paths', severity: 2 }),
    ]));
  });
});
