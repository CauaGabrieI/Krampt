(function () {
  const ultima = document.querySelector('.dm-thread .dm-bubble:last-of-type');
  const thread = document.querySelector('.dm-thread');
  if (ultima && thread) thread.scrollTop = thread.scrollHeight;
  const input = document.querySelector('.dm-composer textarea');
  const composer = document.querySelector('.dm-composer');
  if (input) {
    input.focus({ preventScroll: true });
    input.addEventListener('keydown', (event) => {
      if (event.key !== 'Enter' || event.shiftKey || event.isComposing) return;
      event.preventDefault();
      composer.requestSubmit();
    });
  }
})();