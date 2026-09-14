document.querySelectorAll('.post-carousel').forEach(carousel => {
  const track = carousel.querySelector('.post-carousel-track');
  const slides = Array.from(track.children);
  const controls = carousel.querySelector('.post-carousel-controls');
  let current = 0;
  function update() {
    slides.forEach((slide, index) => { slide.hidden = index !== current; });
    if (!controls) return;
    controls.querySelector('.post-carousel-count').textContent = `${current + 1} / ${slides.length}`;
    controls.querySelector('[data-carousel-step="-1"]').disabled = current === 0;
    controls.querySelector('[data-carousel-step="1"]').disabled = current === slides.length - 1;
  }
  function go(index) {
    current = Math.max(0, Math.min(slides.length - 1, index));
    update();
  }
  carousel.classList.add('is-ready');
  if (controls) {
    controls.hidden = false;
    controls.querySelectorAll('button').forEach(button => {
      button.addEventListener('click', () => go(current + Number(button.dataset.carouselStep)));
    });
  }
  track.addEventListener('keydown', event => {
    if (event.key === 'ArrowRight' || event.key === 'ArrowLeft') {
      event.preventDefault();
      go(current + (event.key === 'ArrowRight' ? 1 : -1));
    }
  });
  update();
  const selected = Number(new URLSearchParams(location.search).get('foto'));
  if (location.pathname.startsWith('/post/') && Number.isInteger(selected) && selected > 0) {
    current = Math.min(selected, slides.length) - 1;
    go(current);
    update();
  }
});
