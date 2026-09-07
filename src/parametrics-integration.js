/* Solve before associations/validation, within the existing rollback boundary. */
(function(root) {
  'use strict';
  const K=root.Kestrel;
  if(!K?.Drawing || !K.Parametrics)throw new Error('Load the drawing model and parametric solver before integration.');
  const prototype=K.Drawing.prototype;
  if(prototype._parametricTransactionInstalled)return;
  const original=prototype.transaction;
  prototype.transaction=function(label,edit) {
    if(typeof edit!=='function')throw new Error('A drawing transaction requires an edit function.');
    return original.call(this,label,()=>{
      edit();
      K.Parametrics.enforce(this);
    });
  };
  Object.defineProperty(prototype,'_parametricTransactionInstalled',{value:true});
})(typeof window!=='undefined'?window:globalThis);
