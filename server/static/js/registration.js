document.addEventListener("DOMContentLoaded", function() {
  handleVaccinationFields();
  handleNotInIndiaField();
});

function handleVaccinationFields() {
  var isVaccinatedCheckbox = document.querySelector("#id_is_vaccinated");
  var vaccinationName = document.querySelector("#id_vaccination_name").parentNode;
  var vaccinationCertificate = document.querySelector("#id_vaccination_certificate").parentNode;
  var explainNotVaccinated = document.querySelector("#id_explain_not_vaccinated").parentNode;

  // Initially hide the vaccination fields and show the explain_not_vaccinated field
  vaccinationName.style.display = "none";
  vaccinationCertificate.style.display = "none";
  explainNotVaccinated.style.display = "block";

  isVaccinatedCheckbox.addEventListener("change", function() {
    if (this.checked) {
      vaccinationName.style.display = "block";
      vaccinationCertificate.style.display = "block";
      explainNotVaccinated.style.display = "none";
    } else {
      vaccinationName.style.display = "none";
      vaccinationCertificate.style.display = "none";
      explainNotVaccinated.style.display = "block";
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
