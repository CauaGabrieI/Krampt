(() => {
  const input = document.getElementById('password');
  const feedback = document.getElementById('password-feedback');
  if (!input || !feedback) return;

  const status = document.getElementById('password-strength');
  const rulesList = document.getElementById('password-rules');

  const rules = {
    length: value => value.length >= 10,
    upper: value => /\p{Lu}/u.test(value),
    lower: value => /\p{Ll}/u.test(value),
    number: value => /\p{Nd}/u.test(value),
    special: value => /[^\p{L}\p{N}\s]/u.test(value),
  };

  const setRulesVisible = visible => {
    if (rulesList) rulesList.hidden = !visible;
  };

  const updateStrength = () => {
    const value = input.value;
    const valid = Object.entries(rules).map(([name, test]) => {
      const passed = test(value);
      feedback
        .querySelector(`[data-rule="${name}"]`)
        ?.classList.toggle('is-met', passed);
      return passed;
    });

    const count = valid.filter(Boolean).length;
    const level = value
      ? (count === 5 ? 'strong' : count >= 3 ? 'medium' : 'weak')
      : 'empty';

    feedback.dataset.strength = level;
    status.textContent = {
      empty: 'Digite uma senha para ver os requisitos.',
      weak: 'Senha fraca',
      medium: 'Senha média',
      strong: 'Senha forte',
    }[level];
  };

  setRulesVisible(false);
  updateStrength();

  input.addEventListener('focus', () => {
    setRulesVisible(true);
  });

  input.addEventListener('blur', () => {
    setRulesVisible(false);
  });

  input.addEventListener('input', updateStrength);
})();
