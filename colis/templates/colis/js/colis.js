// ~/ebi3/colis/static/colis/js/colis.js
// JavaScript spécifique à l'application colis

$(document).ready(function() {
    // Initialisation des tooltips
    $('[data-bs-toggle="tooltip"]').tooltip();

    // Gestion des favoris
    $('.favorite-btn').click(function(e) {
        e.preventDefault();
        const btn = $(this);
        const url = btn.data('url');

        $.ajax({
            url: url,
            type: 'POST',
            data: {
                csrfmiddlewaretoken: document.querySelector('[name=csrfmiddlewaretoken]').value
            },
            success: function(data) {
                if (data.status === 'success') {
                    btn.toggleClass('btn-danger btn-outline-danger');
                    btn.find('i').toggleClass('fas far');

                    // Afficher notification
                    showToast(
                        data.action === 'added' ?
                        'Colis ajouté aux favoris' :
                        'Colis retiré des favoris',
                        'success'
                    );
                }
            }
        });
    });

    // Calcul de volume automatique
    $('.dimension-input').on('input', function() {
        const length = parseFloat($('#id_length').val()) || 0;
        const width = parseFloat($('#id_width').val()) || 0;
        const height = parseFloat($('#id_height').val()) || 0;

        if (length > 0 && width > 0 && height > 0) {
            const volume = (length * width * height) / 1000;
            $('#volume-preview').text(volume.toFixed(2) + ' L').removeClass('d-none');
        }
    });

    // Fonction pour afficher des toasts
    function showToast(message, type) {
        const toastHtml = `
            <div class="toast align-items-center text-white bg-${type} border-0" role="alert">
                <div class="d-flex">
                    <div class="toast-body">
                        ${message}
                    </div>
                    <button type="button" class="btn-close btn-close-white me-2 m-auto" data-bs-dismiss="toast"></button>
                </div>
            </div>
        `;

        if ($('#toast-container').length === 0) {
            $('body').append('<div id="toast-container" class="toast-container position-fixed top-0 end-0 p-3"></div>');
        }

        $('#toast-container').append(toastHtml);
        $('.toast').toast('show');

        $('.toast').on('hidden.bs.toast', function() {
            $(this).remove();
        });
    }

    // Initialiser le sélecteur de date avec des limites
    const today = new Date().toISOString().split('T')[0];
    $('input[type="date"][min]').attr('min', today);

    // Gestion des modales de connexion
    $('.requires-login').click(function(e) {
        if (!window.userAuthenticated) {
            e.preventDefault();
            $('#loginModal').modal('show');
        }
    });
});