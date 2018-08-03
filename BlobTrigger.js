module.exports = function (context, myBlob) {
    context.bindings.outputQueueItem = context.bindingData.name;
    context.log("JavaScript blob trigger function processed blob \n Name:", context.bindingData.name, "\n Blob Size:", myBlob.length, "Bytes");
    context.done();
};
