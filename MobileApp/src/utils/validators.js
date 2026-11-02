// Placeholder for client-side validation (SCRUM-50), mirroring the rules in
// Server/accounts/validators.py — fails fast before hitting the network;
// the backend stays the source of truth.
//
// Will hold:
// - validateEmail(email)
// - validatePassword(password)        -> min length only, mirrors MinimumLengthValidator
// - validateBirthDate(birthDate)       -> min age 16
// - validateHeight(heightCm)           -> 100-250cm
// - validatePhone(value)               -> Danish 8-digit numbers
