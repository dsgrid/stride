// Fix tab order for project switcher - input -> button -> dropdown
document.addEventListener('DOMContentLoaded', function() {
    function setupTabHandler() {
        var input = document.getElementById('project-path-input');
        var button = document.getElementById('load-project-btn');

        if (input && button) {
            input.addEventListener('keydown', function(e) {
                if (e.key === 'Tab' && !e.shiftKey) {
                    e.preventDefault();
                    button.focus();
                }
            });
        }
    }

    // Run after delays to ensure elements are rendered
    setTimeout(setupTabHandler, 100);
    setTimeout(setupTabHandler, 500);
    setTimeout(setupTabHandler, 1000);
});
