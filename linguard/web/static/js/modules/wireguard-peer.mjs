import {prependAlert} from "./utils.mjs";

const alertContainer = "alerts";

document.getElementById('private_key').setAttribute('type', "password");

document.getElementById("togglePrivateKey").addEventListener("click", function () {
    const icon = document.getElementById('togglePrivateKeyIcon')
    const field = document.getElementById('private_key');
    const type = field.getAttribute('type') === 'password' ? 'text' : 'password';
    field.setAttribute('type', type);
    if (type === "password") {
        icon.classList.add('fa-eye-slash');
        icon.classList.remove('fa-eye');
    }
    else {
        icon.classList.add('fa-eye');
        icon.classList.remove('fa-eye-slash');
    }
}, false);

document.getElementById("removePeer").addEventListener("click", function () {
    const alertType = "danger";
    $.ajax({
        type: "delete",
        url: location.href,
        success: function (resp) {
            location.replace("/wireguard");
        },
        error: function(resp) {
            prependAlert(alertContainer, "<strong>Oops, something went wrong</strong>: " + resp["responseText"],
                alertType);
            $("#removeModal").modal("toggle");
        },
    });
});