export function confirmCardAction(text){
  return new Promise(resolve=>{
    const dialog=document.createElement('dialog');
    dialog.className='rounded-xl p-6 border border-slate-300 max-w-lg';
    dialog.setAttribute('aria-label','Xác nhận thao tác thẻ');
    const message=document.createElement('p');message.textContent=text;
    const cancel=document.createElement('button');cancel.type='button';cancel.textContent='Hủy';cancel.className='border rounded-lg px-4 py-2 mt-4 mr-3';
    const accept=document.createElement('button');accept.type='button';accept.textContent='Xác nhận';accept.className='bg-red-700 text-white rounded-lg px-4 py-2 mt-4';
    const finish=value=>{dialog.close();dialog.remove();resolve(value);};
    cancel.onclick=()=>finish(false);accept.onclick=()=>finish(true);
    dialog.addEventListener('cancel',e=>{e.preventDefault();finish(false);});
    dialog.append(message,cancel,accept);document.body.append(dialog);dialog.showModal();cancel.focus();
  });
}
