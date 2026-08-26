$(document).ready(function () {
    $('#dictionary-table').DataTable({
        dom: 'ltrip',
        language: {
            lengthMenu: 'Показать _MENU_ записей',
            info: 'Показано _START_ до _END_ из _TOTAL_ записей',
            paginate: {
                previous: 'Назад',
                next: 'Вперед',
            },
        },
        fixedHeader: true,
        orderCellsTop: true,
        initComplete: function () {
            const api = this.api();
            api.columns().every(function (columnIndex) {
                if (columnIndex >= 2) {
                    return;
                }

                const cell = $('thead tr:eq(1) th').eq(columnIndex);
                cell.empty();
                const input = $('<input>', {
                    type: 'text',
                    placeholder: '',
                }).appendTo(cell);

                input.on('keyup change', function () {
                    if (api.column(columnIndex).search() !== this.value) {
                        api.column(columnIndex).search(this.value).draw();
                    }
                });
            });
        },
    });
});
