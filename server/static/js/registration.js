document.addEventListener("DOMContentLoaded", function() {
  handleVaccinationFields();
  handleNotInIndiaField();
});

function handleVaccinationFields() {
  var vaccinationFieldsContainer = document.getElementById("vaccination-fields-container");
  var explainNotVaccinatedContainer = document.getElementById("explain-not-vaccinated-container");
  var isVaccinatedCheckbox = document.getElementById("id_is_vaccinated");

  // Initially hide the vaccination fields and show the explain_not_vaccinated field
  vaccinationFieldsContainer.style.display = "none";
  explainNotVaccinatedContainer.style.display = "block";

  isVaccinatedCheckbox.addEventListener("change", function() {
    if (this.checked) {
      vaccinationFieldsContainer.style.display = "block";
      explainNotVaccinatedContainer.style.display = "none";
    } else {
      vaccinationFieldsContainer.style.display = "none";
      explainNotVaccinatedContainer.style.display = "block";
    }
  });
}

function handleNotInIndiaField() {
  var notInIndiaCheckbox = document.getElementById("id_not_in_india");
  var stateUTField = document.getElementById("id_state_ut");

  // Initially show state_ut field
  stateUTField.style.display = "block";

  notInIndiaCheckbox.addEventListener("change", function() {
    if (this.checked) {
      stateUTField.style.display = "none";
    } else {
      stateUTField.style.display = "block";
    }
  });
}
