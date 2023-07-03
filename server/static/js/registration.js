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
  var notInIndiaCheckbox = document.querySelector("#id_not_in_india");
  var stateUTFieldContainer = document.querySelector("#id_state_ut").parentNode; // Comment this line for Method 2

  // Method 2: uncomment following lines
  // var stateUTField = document.querySelector("#id_state_ut");
  // var stateUTLabel = document.querySelector("label[for='id_state_ut']");

  // Initially show state_ut field and title
  stateUTFieldContainer.style.display = "block";
  // Method 2: uncomment following line
  // stateUTLabel.style.display = "block";

  notInIndiaCheckbox.addEventListener("change", function() {
    if (this.checked) {
      stateUTFieldContainer.style.display = "none";
      // Method 2: uncomment following line
      // stateUTLabel.style.display = "none";
    } else {
      stateUTFieldContainer.style.display = "block";
      // Method 2: uncomment following line
      // stateUTLabel.style.display = "block";
    }
  });
}
