import {postJSON, prependAlert} from "./utils.mjs";

const gwIface = $("#gateway");
const onUp = $("#on_up")
const onDown = $("#on_down")
const alertContainer = "wgIfaceConfig";

let oldGw = gwIface.val();

function replaceOnUpDownComands(oldVal, newVal) {
    let value = onUp.val();
    value = value.replace(new RegExp(oldVal), newVal);
    onUp.val(value);

    value = onDown.val();
    value = value.replace(new RegExp(oldVal), newVal);
    onDown.val(value);
}

gwIface.change(function () {
    const newGw = gwIface.val();
    if (!newGw) return;
    replaceOnUpDownComands(oldGw, newGw);
    oldGw = newGw;
});

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

const removeIfaceBtn = $(".removeIfaceBtn");
removeItem(removeIfaceBtn, "interface", function () {
    location.replace(document.referrer);
});

const removePeerBtn = $(".removePeerBtn");
removeItem(removePeerBtn, "peer", function () {
    location.reload();
});

function removeItem(removeBtn, itemType, onSuccess) {
    removeBtn.click(function (e) {
        const item = e.target.id.split("-")[1];
        const url = "/wireguard/"+itemType+"s/"+item+"/remove";
        const alertType = "danger";
        $.ajax({
            type: "delete",
            url: url,
            success: onSuccess,
            error: function(resp) {
                prependAlert(alertContainer, "<strong>Oops, something went wrong</strong>: " + resp["responseText"],
                    alertType);
                $("#removeModal").modal("toggle");
            },
        });
    });
}

const downloadBtn = $(".downloadBtn");
downloadBtn.click(function (e) {
    let item = e.target.id.split("-")[1];
    if (!item) {
        item = e.target.farthestViewportElement.id.split("-")[1];
    }
    const url = "/wireguard/peers/"+item+"/download";
    location.replace(url);
});

const startOrStopIfaceBtn = $(".startOrStopIfaceBtn");
startOrStopIfaceBtn.click(function (e) {
    const button = e.target;
    const iface = button.value;
    const action = button.innerText;

    const url = `/wireguard/interfaces/${iface}/${action}`;
    const alertContainer = "wgIfacesHeader";
    const alertType = "danger";
    const loadFeedback = "wgIface-" + iface + "-loading"

    postJSON(url, alertContainer, alertType, loadFeedback);
});