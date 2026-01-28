// Basic client-side validation and password match check
document.addEventListener('submit', function(e){
  const form = e.target;
  if(form.id === 'registerForm'){
    const p = form.querySelector('#password');
    const c = form.querySelector('#confirm_password');
    const email = form.querySelector('#email');
    if(p && c && p.value !== c.value){
      e.preventDefault();
      alert('Passwords do not match.');
      return false;
    }
    if(p && p.value.length < 8){
      e.preventDefault();
      alert('Password must be at least 8 characters.');
      return false;
    }
    if(email && email.value){
      const re = /^[^@\s]+@[^@\s]+\.[^@\s]+$/;
      if(!re.test(email.value)){
        e.preventDefault();
        alert('Please enter a valid email address.');
        return false;
      }
    }
  }

  if(form.id === 'adminEditForm'){
    // Validate new password length if provided
    const newpw = form.querySelector('input[name="new_password"]');
    if(newpw && newpw.value){
      if(newpw.value.length < 8){
        e.preventDefault();
        alert('New password must be at least 8 characters.');
        return false;
      }
    }

    // Validate email field if present
    const email = form.querySelector('input[name="email"]');
    if(email && email.value){
      const re = /^[^@\s]+@[^@\s]+\.[^@\s]+$/;
      if(!re.test(email.value)){
        e.preventDefault();
        alert('Please enter a valid email address.');
        return false;
      }
    }

    // Validate JSON textareas
    const textareas = form.querySelectorAll('textarea');
    for(const ta of textareas){
      const v = ta.value.trim();
      if(v){
        try{
          JSON.parse(v);
        }catch(err){
          e.preventDefault();
          alert('Invalid JSON in field: ' + (ta.name || '')); 
          return false;
        }
      }
    }
  }
  // allow form to submit otherwise
});
